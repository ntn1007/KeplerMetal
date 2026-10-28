#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run the previous five-function CAS SDK client under a no-kill lab lease."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def need(value,message):
    if not value:raise ValueError(message)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('lab','build','out'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--mode',choices=('negative','prepare','native','execute'),required=True)
    args=parser.parse_args();lab=args.lab.resolve();build=args.build.resolve();out=args.out.resolve()
    out.relative_to(lab/'results');need(not out.exists(),'fresh output required')
    inputs=json.loads((build/'inputs.json').read_text())
    for name,digest in inputs['frozen'].items():need(sha(build/name)==digest,'build input changed: '+name)
    need(sha(build/'client/cas_example')==inputs['executable_SHA256'] and os.getuid()==inputs['user_UID'],
         'executable or user changed')
    sys.path.insert(0,str(build/'support'))
    from video_metal_resource_observer import check_profile
    from verify_native_cas_sdk import verify
    need(check_profile()==inputs['profile'],'machine profile changed')
    module=lab/'results/video-rm-access-build-20261018-03/runtime/lab_gpu_reservation.py'
    need(sha(module)=='ee637d27c5af482b1fbce396f6a49ef234b09a7d8602aeb36edc422f46b61248',
         'reservation module changed')
    spec=importlib.util.spec_from_file_location('lab_gpu_reservation',module)
    reservation=importlib.util.module_from_spec(spec);spec.loader.exec_module(reservation)
    lease=reservation.GPUReservation(lab);child=None
    try:
        out.mkdir();shutil.copytree(build/'sdk/assets',out/'assets');(out/'outputs').mkdir();execution=out/'execution';execution.mkdir()
        signed=execution/'application';shutil.copyfile(build/'client/cas_example',signed);signed.chmod(0o755)
        subprocess.run(['codesign','--force','--sign','-',str(signed)],capture_output=True,check=True,timeout=15)
        subprocess.run(['codesign','--verify','--strict',str(signed)],capture_output=True,check=True,timeout=15)
        lease.spawning(signed,sha(signed));registry=lab/'results/signed-native-jobs.json'
        jobs=json.loads(registry.read_text()) if registry.exists() else []
        argv=[str(out/'assets'),str(out/'assets/client-manifest.json'),str(out/'outputs'),args.mode]
        with (execution/'execution.stdout').open('wb') as stdout,(execution/'execution.stderr').open('wb') as stderr:
            child=subprocess.Popen([str(signed),*argv],stdout=stdout,stderr=stderr,pass_fds=(lease.fd,))
            lease.bind_child(child.pid)
            job={'started_at':now(),'pid':child.pid,'original_executable':str(build/'client/cas_example'),
                 'original_binary_sha256':inputs['executable_SHA256'],'signed_executable':str(signed),
                 'signed_binary_sha256':sha(signed),'arguments':argv}
            jobs.append(job);registry.write_text(json.dumps(jobs,indent=2)+'\n')
            print(json.dumps({'status':'STARTED','pid':child.pid}),flush=True)
            code=child.wait() # No forced timeout or kill.
        ps=subprocess.run(['ps','-p',str(child.pid),'-o','pid=,lstart=,command='],capture_output=True,text=True,timeout=10)
        need(ps.returncode in (0,1) and not ps.stderr,'process state unavailable')
        state=ps.stdout.strip();job.update(exit_code=code,SIGKILL_requested=False,
                                           authoritative_ps_status=state,completed_at=now())
        registry.write_text(json.dumps(jobs,indent=2)+'\n');lease.finish(code,False,state)
        (execution/'manifest.json').write_text(json.dumps({**job,'GPU_reservation':dict(lease.data)},indent=2)+'\n')
        need(code==0 and not state,'host did not finish cleanly')
        need(check_profile()==inputs['profile'],'machine profile changed during host')
        (out/'results.json').write_bytes((execution/'execution.stdout').read_bytes())
        verification=verify(out)
        (out/'independent-verification.json').write_text(json.dumps(verification,indent=2)+'\n')
        print(json.dumps({k:v for k,v in verification.items() if k!='records'}),flush=True)
    except BaseException:
        if child is not None and child.poll() is None:lease.finish(None,False,'child outcome unresolved')
        raise
    finally:lease.close()


if __name__=='__main__':main()
