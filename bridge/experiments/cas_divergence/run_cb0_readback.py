#!/usr/bin/env python3
"""Execute one pinned CB0 witness under the common no-kill GPU lease."""
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
from run_repair import PINS,SYSTEM
from verify_cb0_readback import verify

HERE=Path(__file__).resolve().parent
BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'tools'))
from recognize_native_cas import verify_decoder

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def need(ok,reason):
    if not ok:raise ValueError(reason)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('lab','build','out'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--mode',choices=('control','cb0'),required=True);p.add_argument('--control-run',type=Path)
    a=p.parse_args();lab=a.lab.resolve();build=a.build.resolve();out=a.out.resolve()
    build.relative_to(lab/'results');out.relative_to(lab/'results');need(not out.exists() and out.parent.is_dir(),'fresh output required')
    profile=json.loads((build/'build.json').read_text())
    for name,digest in profile['files_SHA256'].items():need(sha(build/name)==digest,'build changed: '+name)
    need(sha(build/'shader.metallib')==PINS['shader.metallib'] and sha(build/'original.sass')==PINS['original.sass'] and
         sha(build/'native.metadata')=='f99b8ca94aec90088ba8aee80c42b9e242a7829a81c3fedbf34b2312b08bacbe' and
         sha(build/'control.sass')=='e7d58f3637b4268c97d2e0a6ec94d9177833ac2747db954b6ec6be37161d4d7e' and
         sha(build/'cb0.sass')=='60291c5a9dde52384a97a31d1edff5c6374d12a1d40a3abfdbd0ed3484099625','input or witness pin differs')
    for name in ('cb0_readback_host.mm','cb0_readback_import.mm'):
        need(sha(build/name)==sha(HERE/name),'witness source differs')
    need(sha(build/'KeplerNativeCAS.mm')==sha(BRIDGE/'src/KeplerNativeCAS.mm') and
         sha(build/'src/KeplerConditionalAux.h')==sha(BRIDGE/'src/KeplerConditionalAux.h') and
         sha(build/'src/KeplerNativeCASAdapter.inc')==sha(BRIDGE/'src/KeplerNativeCASAdapter.inc'),'runtime differs')
    decoder=lab/'build/envydis-only/envydis/envydis'
    for name in ('control','cb0'):
        need(verify_decoder((build/(name+'.sass')).read_bytes(),(build/(name+'.asm')).read_text(),decoder),'decoder replay failed')
    if a.mode=='cb0':
        need(a.control_run is not None,'passing known-value control required')
        root=a.control_run.resolve();root.relative_to(lab/'results');m=json.loads((root/'manifest.json').read_text())
        report=json.loads((root/'report.json').read_text());oracle=verify((root/'output.bin').read_bytes(),report)
        need(m['mode']=='control' and m['exit_code']==0 and m['GPU_reservation']['state']=='terminal' and
             not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and m['build_sha256']==sha(build/'build.json') and
             m['signed_binary_sha256']==sha(root/'application') and oracle['status']=='PASS','known-value control not qualified')
    before={path:sha(path) for path in SYSTEM};need(before==SYSTEM,'system profile differs')
    module=lab/'results/video-rm-access-build-20261018-03/runtime/lab_gpu_reservation.py'
    need(sha(module)=='ee637d27c5af482b1fbce396f6a49ef234b09a7d8602aeb36edc422f46b61248','lease differs')
    spec=importlib.util.spec_from_file_location('lab_gpu_reservation',module);reservation=importlib.util.module_from_spec(spec);spec.loader.exec_module(reservation)
    lease=reservation.GPUReservation(lab);child=None
    try:
        out.mkdir();binary=out/'application';shutil.copyfile(build/'host',binary);binary.chmod(0o755)
        need(sha(binary)==profile['files_SHA256']['host'],'host snapshot differs')
        subprocess.run(['codesign','--force','--sign','-',str(binary)],capture_output=True,check=True,timeout=15)
        subprocess.run(['codesign','--verify','--strict',str(binary)],capture_output=True,check=True,timeout=15)
        lease.spawning(binary,sha(binary));registry=lab/'results/signed-native-jobs.json'
        jobs=json.loads(registry.read_text()) if registry.exists() else []
        args=[str(out),a.mode,str(build/'shader.metallib'),str(build/'native.metadata'),str(build/'original.sass'),str(build/(a.mode+'.sass'))]
        env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','LD_','KM_CAS_'))}
        with (out/'report.json').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
            child=subprocess.Popen([str(binary),*args],stdout=stdout,stderr=stderr,pass_fds=(lease.fd,),env=env)
            lease.bind_child(child.pid);job={'started_at':now(),'pid':child.pid,'original_executable':str(build/'host'),
                'original_binary_sha256':profile['files_SHA256']['host'],'signed_executable':str(binary),
                'signed_binary_sha256':sha(binary),'arguments':args}
            jobs.append(job);registry.write_text(json.dumps(jobs,indent=2)+'\n')
            print(json.dumps({'status':'STARTED','pid':child.pid,'mode':a.mode}),flush=True);code=child.wait()
        ps=subprocess.run(['ps','-p',str(child.pid),'-o','pid=,lstart=,command='],capture_output=True,text=True,timeout=10)
        need(ps.returncode in (0,1) and not ps.stderr,'process status unavailable');state=ps.stdout.strip()
        job.update(exit_code=code,SIGKILL_requested=False,authoritative_ps_status=state,completed_at=now())
        registry.write_text(json.dumps(jobs,indent=2)+'\n');lease.finish(code,False,state)
        after={path:sha(path) for path in SYSTEM}
        (out/'manifest.json').write_text(json.dumps({**job,'mode':a.mode,'GPU_reservation':dict(lease.data),
             'system_before':before,'system_after':after,'build_sha256':sha(build/'build.json')},indent=2)+'\n')
        need(code==0 and not state and before==after,'witness failed or profile changed')
        for name,digest in profile['files_SHA256'].items():need(sha(build/name)==digest,'build changed: '+name)
        report=json.loads((out/'report.json').read_text());proof=report['import'];events=proof['events']
        need(proof['contract_verified'] and proof['constructor_restored'] and len(events)==1 and
             events[0]['conditional_auxiliary_section_pinned'] and events[0]['expected_original_code_identical'] and
             events[0]['native_metadata_identical_to_certificate'] and events[0]['imported_code_identical'], 'import evidence differs')
        result=verify((out/'output.bin').read_bytes(),report)
        (out/'verified.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
        print(json.dumps({'status':'TERMINAL','mode':a.mode,'result':result['status']}),flush=True)
    except BaseException:
        if child is not None and child.poll() is None:lease.finish(None,False,'child outcome not established')
        raise
    finally:lease.close()

if __name__=='__main__':main()
