#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Capture one native compiler output under the cooperative no-kill lab lease."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import shutil
import struct
import subprocess
from pathlib import Path


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def need(value,message):
    if not value:raise ValueError(message)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('lab','library','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();lab=a.lab.resolve();library=a.library.resolve();out=a.out.resolve()
    library.relative_to(lab/'results');out.relative_to(lab/'results')
    need(not out.exists() and out.parent.is_dir(),'fresh output required')
    module=lab/'results/video-rm-access-build-20261018-03/runtime/lab_gpu_reservation.py'
    need(sha(module)=='ee637d27c5af482b1fbce396f6a49ef234b09a7d8602aeb36edc422f46b61248','reservation differs')
    executable=lab/'build/compiler_output_trace';exe_sha=sha(executable);library_sha=sha(library)
    spec=importlib.util.spec_from_file_location('lab_gpu_reservation',module)
    reservation=importlib.util.module_from_spec(spec);spec.loader.exec_module(reservation)
    lease=reservation.GPUReservation(lab);child=None
    try:
        out.mkdir();binary=out/'application';snapshot=out/'input.metallib';capture=out/'capture';capture.mkdir()
        shutil.copyfile(executable,binary);shutil.copyfile(library,snapshot);binary.chmod(0o755)
        need(sha(binary)==exe_sha and sha(snapshot)==library_sha,'snapshot mismatch')
        subprocess.run(['codesign','--force','--sign','-',str(binary)],capture_output=True,check=True,timeout=15)
        subprocess.run(['codesign','--verify','--strict',str(binary)],capture_output=True,check=True,timeout=15)
        lease.spawning(binary,sha(binary));registry=lab/'results/signed-native-jobs.json'
        jobs=json.loads(registry.read_text()) if registry.exists() else []
        argv=[str(snapshot),str(capture),'compute','divergence_case']
        with (out/'capture.stdout').open('wb') as stdout,(out/'capture.stderr').open('wb') as stderr:
            child=subprocess.Popen([str(binary),*argv],stdout=stdout,stderr=stderr,pass_fds=(lease.fd,))
            lease.bind_child(child.pid)
            job={'started_at':now(),'pid':child.pid,'original_executable':str(executable),'original_binary_sha256':exe_sha,
                 'signed_executable':str(binary),'signed_binary_sha256':sha(binary),'arguments':argv}
            jobs.append(job);registry.write_text(json.dumps(jobs,indent=2)+'\n')
            print(json.dumps({'status':'STARTED','pid':child.pid}),flush=True)
            code=child.wait() # No timeout, signal or retry.
        ps=subprocess.run(['ps','-p',str(child.pid),'-o','pid=,lstart=,command='],capture_output=True,text=True,timeout=10)
        need(ps.returncode in (0,1) and not ps.stderr,'process state unavailable')
        state=ps.stdout.strip();job.update(exit_code=code,SIGKILL_requested=False,authoritative_ps_status=state,completed_at=now())
        registry.write_text(json.dumps(jobs,indent=2)+'\n');lease.finish(code,False,state)
        (out/'manifest.json').write_text(json.dumps({**job,'GPU_reservation':dict(lease.data),
            'library_SHA256':library_sha,'runner_SHA256':sha(__file__)},indent=2)+'\n')
        need(code==0 and not state and sha(snapshot)==library_sha,'capture failed or input changed')
        report=json.loads((out/'capture.stdout').read_text())
        need(report['pipeline_created'] and not report['gpu_dispatch'] and len(report['captures'])==1,'unexpected capture')
        blob=Path(report['captures'][0]['file']).read_bytes();need(len(blob)>=32,'short native container')
        offset=8;sections={};seen=set()
        while True:
            need(offset not in seen and offset<=len(blob)-16,'invalid section link');seen.add(offset)
            nxt,kind,size=struct.unpack_from('<QII',blob,offset);need(size<=len(blob)-offset-16,'short section')
            if kind in (0x10004,0x10005):
                need(kind not in sections,'duplicate section');sections[kind]=blob[offset+16:offset+16+size]
            if not nxt:break
            need(nxt>=16+size and nxt<=len(blob)-offset,'invalid next offset');offset+=nxt
        need(set(sections)=={0x10004,0x10005} and len(sections[0x10004])==232 and len(sections[0x10005])%64==0,
             'unexpected native sections')
        (out/'native.sass').write_bytes(sections[0x10005]);(out/'native.metadata').write_bytes(sections[0x10004])
        print(json.dumps({'status':'CAPTURED','gpu_dispatch':False,'native_SHA256':sha(out/'native.sass'),
                          'metadata_SHA256':sha(out/'native.metadata'),'library_SHA256':library_sha}),flush=True)
    except BaseException:
        if child is not None and child.poll() is None:lease.finish(None,False,'child outcome not established')
        raise
    finally:lease.close()


if __name__=='__main__':main()
