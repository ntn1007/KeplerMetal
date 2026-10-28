#!/usr/bin/env python3
"""Run a signed passive command observer under the shared no-kill lease."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path
from run_repair import SYSTEM

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def need(ok,reason):
    if not ok:raise ValueError(reason)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('lab','build','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--mode',choices=('native','repaired'),required=True);a=p.parse_args()
    lab=a.lab.resolve();build=a.build.resolve();out=a.out.resolve()
    build.relative_to(lab/'results');out.relative_to(lab/'results')
    need(not out.exists() and out.parent.is_dir(),'fresh output required')
    inputs=json.loads((build/'build.json').read_text())
    for name,digest in inputs['files_SHA256'].items():need(sha(build/name)==digest,'build differs: '+name)
    before={path:sha(path) for path in SYSTEM};need(before==SYSTEM,'system profile differs')
    module=lab/'results/video-rm-access-build-20261018-03/runtime/lab_gpu_reservation.py'
    need(sha(module)=='ee637d27c5af482b1fbce396f6a49ef234b09a7d8602aeb36edc422f46b61248','lease differs')
    spec=importlib.util.spec_from_file_location('lab_gpu_reservation',module)
    reservation=importlib.util.module_from_spec(spec);spec.loader.exec_module(reservation)
    lease=reservation.GPUReservation(lab);child=None
    try:
        out.mkdir();binary=out/'application';shutil.copyfile(build/'host',binary);binary.chmod(0o755)
        need(sha(binary)==inputs['files_SHA256']['host'],'host snapshot differs')
        subprocess.run(['codesign','--force','--sign','-',str(binary)],capture_output=True,check=True,timeout=15)
        subprocess.run(['codesign','--verify','--strict',str(binary)],capture_output=True,check=True,timeout=15)
        lease.spawning(binary,sha(binary));registry=lab/'results/signed-native-jobs.json'
        jobs=json.loads(registry.read_text()) if registry.exists() else []
        args=[str(build/'shader.metallib'),str(out),a.mode,str(build/'original.sass'),str(build/'repaired.sass')]
        env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','LD_','KM_CAS_'))}
        env['KM_CAS_CONDITIONAL_CERT']=str(build/'certificate.json')
        with (out/'report.json').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
            child=subprocess.Popen([str(binary),*args],stdout=stdout,stderr=stderr,pass_fds=(lease.fd,),env=env)
            lease.bind_child(child.pid);job={'started_at':now(),'pid':child.pid,'original_executable':str(build/'host'),
                'original_binary_sha256':inputs['files_SHA256']['host'],'signed_executable':str(binary),
                'signed_binary_sha256':sha(binary),'arguments':args}
            jobs.append(job);registry.write_text(json.dumps(jobs,indent=2)+'\n')
            print(json.dumps({'status':'STARTED','pid':child.pid,'mode':a.mode}),flush=True)
            code=child.wait()
        ps=subprocess.run(['ps','-p',str(child.pid),'-o','pid=,lstart=,command='],capture_output=True,text=True,timeout=10)
        need(ps.returncode in (0,1) and not ps.stderr,'process status unavailable');state=ps.stdout.strip()
        job.update(exit_code=code,SIGKILL_requested=False,authoritative_ps_status=state,completed_at=now())
        registry.write_text(json.dumps(jobs,indent=2)+'\n');lease.finish(code,False,state)
        after={path:sha(path) for path in SYSTEM}
        (out/'manifest.json').write_text(json.dumps({**job,'mode':a.mode,'GPU_reservation':dict(lease.data),
             'system_before':before,'system_after':after,'build_sha256':sha(build/'build.json')},indent=2)+'\n')
        need(code==0 and not state and after==before,'observer failed or profile changed')
        for name,digest in inputs['files_SHA256'].items():need(sha(build/name)==digest,'build changed: '+name)
        report=json.loads((out/'report.json').read_text())
        need(report['status']=='PREPARED_NOT_SUBMITTED' and report['mode']==a.mode and
             report['GPU_submissions']==0 and not report['GPU_execution_proved'] and report['command_status']==0,
             'unexpected observation status')
        for name,key in (('commands','command_SHA256'),('variant','variant_SHA256')):
            need(sha(out/(name+'.bin'))==report[key],'raw observation changed')
        print(json.dumps({'status':'TERMINAL','mode':a.mode,'GPU_submissions':0}),flush=True)
    except BaseException:
        if child is not None and child.poll() is None:lease.finish(None,False,'child outcome not established')
        raise
    finally:lease.close()

if __name__=='__main__':main()
