#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run the conditional-CAS SDK host under the common no-kill lab lease."""
import argparse
import base64
import datetime
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path
from run_repair import PINS,SYSTEM


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def need(value,message):
    if not value:raise ValueError(message)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('lab','build','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--mode',choices=('native','repaired','negative-pin','negative-nop','negative-profile','negative-metadata','negative-air'),required=True)
    a=p.parse_args();lab=a.lab.resolve();build=a.build.resolve();out=a.out.resolve()
    build.relative_to(lab/'results');out.relative_to(lab/'results')
    need(not out.exists() and out.parent.is_dir(),'fresh output required')
    for name,digest in PINS.items():need(sha(build/name)==digest,'program or library differs: '+name)
    system_before={path:sha(path) for path in SYSTEM};need(system_before==SYSTEM,'system profile differs')
    base=json.loads((build/'build.json').read_text());sdk=json.loads((build/'sdk-build.json').read_text())
    for name,digest in base['files_SHA256'].items():need(sha(build/name)==digest,'build snapshot differs: '+name)
    for name,key in [('host-sdk','host_SHA256'),('sdk_host.mm','host_source_SHA256'),
                     ('sdk_wrapper.mm','wrapper_SHA256'),('src/KeplerNativeCASAdapter.inc','adapter_SHA256'),
                     ('certificate.json','certificate_SHA256')]:need(sha(build/name)==sdk[key],'SDK snapshot differs: '+name)
    module=lab/'results/video-rm-access-build-20261018-03/runtime/lab_gpu_reservation.py'
    need(sha(module)=='ee637d27c5af482b1fbce396f6a49ef234b09a7d8602aeb36edc422f46b61248','reservation differs')
    spec=importlib.util.spec_from_file_location('lab_gpu_reservation',module)
    reservation=importlib.util.module_from_spec(spec);spec.loader.exec_module(reservation)
    lease=reservation.GPUReservation(lab);child=None
    try:
        out.mkdir();(out/'outputs').mkdir();binary=out/'application';library=out/'shader.metallib'
        shutil.copyfile(build/'host-sdk',binary);shutil.copyfile(build/'shader.metallib',library);binary.chmod(0o755)
        need(sha(binary)==sdk['host_SHA256'] and sha(library)==PINS['shader.metallib'],'snapshot differs')
        cert=json.loads((build/'certificate.json').read_text())
        if a.mode=='negative-profile':cert['repair_profile']='unqualified-other'
        if a.mode=='negative-air':cert['AIR']['qualified']=True
        if a.mode=='negative-metadata':
            metadata=bytearray(base64.b64decode(cert['native_metadata_base64']));metadata[100]^=1
            cert['native_metadata_base64']=base64.b64encode(metadata).decode()
            cert['native_metadata_SHA256']=hashlib.sha256(metadata).hexdigest()
        certificate=out/'certificate.json';certificate.write_text(json.dumps(cert,indent=2)+'\n');certificate_sha=sha(certificate)
        subprocess.run(['codesign','--force','--sign','-',str(binary)],capture_output=True,check=True,timeout=15)
        subprocess.run(['codesign','--verify','--strict',str(binary)],capture_output=True,check=True,timeout=15)
        lease.spawning(binary,sha(binary));registry=lab/'results/signed-native-jobs.json'
        jobs=json.loads(registry.read_text()) if registry.exists() else []
        host_mode={'negative-nop':'trampoline','negative-profile':'repaired',
                   'negative-metadata':'repaired','negative-air':'repaired'}.get(a.mode,a.mode)
        original='wrong-original.sass' if a.mode=='negative-pin' else 'original.sass'
        replacement='trampoline.sass' if a.mode=='negative-nop' else 'original.sass' if a.mode=='native' else 'repaired.sass'
        argv=[str(library),str(out/'outputs'),host_mode,str(build/original),str(build/replacement)]
        env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','LD_','KM_CAS_'))}
        env['KM_CAS_CONDITIONAL_CERT']=str(certificate)
        with (out/'report.json').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
            child=subprocess.Popen([str(binary),*argv],stdout=stdout,stderr=stderr,pass_fds=(lease.fd,),env=env)
            lease.bind_child(child.pid)
            job={'started_at':now(),'pid':child.pid,'original_executable':str(build/'host-sdk'),
                 'original_binary_sha256':sdk['host_SHA256'],'signed_executable':str(binary),
                 'signed_binary_sha256':sha(binary),'arguments':argv}
            jobs.append(job);registry.write_text(json.dumps(jobs,indent=2)+'\n')
            print(json.dumps({'status':'STARTED','pid':child.pid,'mode':a.mode}),flush=True)
            code=child.wait()
        ps=subprocess.run(['ps','-p',str(child.pid),'-o','pid=,lstart=,command='],capture_output=True,text=True,timeout=10)
        need(ps.returncode in (0,1) and not ps.stderr,'cannot confirm process state')
        state=ps.stdout.strip();job.update(exit_code=code,SIGKILL_requested=False,authoritative_ps_status=state,completed_at=now())
        registry.write_text(json.dumps(jobs,indent=2)+'\n');lease.finish(code,False,state)
        system_after={path:sha(path) for path in SYSTEM}
        (out/'manifest.json').write_text(json.dumps({**job,'test_mode':a.mode,'GPU_reservation':dict(lease.data),
            'SDK_build_SHA256':sha(build/'sdk-build.json'),'certificate_template_SHA256':certificate_sha,
            'runner_SHA256':sha(__file__),'system_before':system_before,'system_after':system_after},indent=2)+'\n')
        negative=a.mode.startswith('negative-')
        need(code==(4 if negative else 0) and not state and system_after==system_before,'unexpected process or profile result')
        need(sha(certificate)==certificate_sha,'certificate template changed')
        for name,digest in PINS.items():need(sha(build/name)==digest,'input changed during execution')
        report=json.loads((out/'report.json').read_text())
        if negative:
            need(report['failure_stage']=='pipeline' and not report['GPU_dispatch'] and
                 not report['import']['gate_accepted'] and not report['import']['constructor_entered'],
                 'negative input not refused before constructor')
        else:need(report['device']=='NVIDIA GeForce GTX 880M' and report['GPU_dispatch'] and len(report['runs'])==48,'unexpected GPU report')
        print(json.dumps({'status':'TERMINAL','mode':a.mode,'exit_code':code,'user_GPU_dispatch':report['GPU_dispatch']}),flush=True)
    except BaseException:
        if child is not None and child.poll() is None:lease.finish(None,False,'child outcome not established')
        raise
    finally:lease.close()


if __name__=='__main__':main()
