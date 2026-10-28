#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run a signed native Metal probe under the common iMac lease without killing it."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def need(value,message):
    if not value:raise ValueError(message)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('lab','build','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();lab=a.lab.resolve();build=a.build.resolve();out=a.out.resolve()
    build.relative_to(lab/'results');out.relative_to(lab/'results')
    need(not out.exists() and out.parent.is_dir(),'fresh output required')
    module=lab/'results/video-rm-access-build-20261018-03/runtime/lab_gpu_reservation.py'
    need(sha(module)=='ee637d27c5af482b1fbce396f6a49ef234b09a7d8602aeb36edc422f46b61248','reservation differs')
    source_hashes={name:sha(build/name) for name in ('host.mm','shader.metal','shader.air','shader.metallib','host')}
    spec=importlib.util.spec_from_file_location('lab_gpu_reservation',module)
    reservation=importlib.util.module_from_spec(spec);spec.loader.exec_module(reservation)
    lease=reservation.GPUReservation(lab);child=None
    try:
        out.mkdir();(out/'outputs').mkdir()
        binary=out/'application';library=out/'shader.metallib'
        shutil.copyfile(build/'host',binary);shutil.copyfile(build/'shader.metallib',library);binary.chmod(0o755)
        need(sha(binary)==source_hashes['host'] and sha(library)==source_hashes['shader.metallib'],'snapshot differs')
        subprocess.run(['codesign','--force','--sign','-',str(binary)],capture_output=True,check=True,timeout=15)
        subprocess.run(['codesign','--verify','--strict',str(binary)],capture_output=True,check=True,timeout=15)
        lease.spawning(binary,sha(binary));registry=lab/'results/signed-native-jobs.json'
        jobs=json.loads(registry.read_text()) if registry.exists() else []
        argv=[str(library),str(out/'outputs'),'880M']
        with (out/'report.json').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
            child=subprocess.Popen([str(binary),*argv],stdout=stdout,stderr=stderr,pass_fds=(lease.fd,))
            lease.bind_child(child.pid)
            job={'started_at':now(),'pid':child.pid,'original_executable':str(build/'host'),
                 'original_binary_sha256':source_hashes['host'],'signed_executable':str(binary),
                 'signed_binary_sha256':sha(binary),'arguments':argv}
            jobs.append(job);registry.write_text(json.dumps(jobs,indent=2)+'\n')
            print(json.dumps({'status':'STARTED','pid':child.pid}),flush=True)
            code=child.wait()  # No timeout, signal or automatic retry.
        ps=subprocess.run(['ps','-p',str(child.pid),'-o','pid=,lstart=,command='],capture_output=True,text=True,timeout=10)
        need(ps.returncode in (0,1) and not ps.stderr,'cannot confirm child state')
        state=ps.stdout.strip();job.update(exit_code=code,SIGKILL_requested=False,authoritative_ps_status=state,completed_at=now())
        registry.write_text(json.dumps(jobs,indent=2)+'\n');lease.finish(code,False,state)
        (out/'manifest.json').write_text(json.dumps({**job,'GPU_reservation':dict(lease.data),
            'source_SHA256':source_hashes,'runner_SHA256':sha(__file__)},indent=2)+'\n')
        need(code==0 and not state,'host did not complete; inspect retained process and logs')
        need(sha(library)==source_hashes['shader.metallib'],'compiled library changed')
        report=json.loads((out/'report.json').read_text());need('880M' in report['device'],'device identity differs')
        print(json.dumps({'status':'TERMINAL','device':report['device'],'dispatches':len(report['runs'])}),flush=True)
    except BaseException:
        if child is not None and child.poll() is None:lease.finish(None,False,'child outcome not established')
        raise
    finally:lease.close()


if __name__=='__main__':main()
