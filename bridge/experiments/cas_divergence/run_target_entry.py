#!/usr/bin/env python3
"""Run one pinned target-entry witness under the cooperative no-kill lease."""
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
from verify_branch_witness import verify_baseline
from verify_target_entry import compare

HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1];sys.path.insert(0,str(BRIDGE/'tools'))
from recognize_native_cas import verify_decoder
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def need(ok,reason):
    if not ok:raise ValueError(reason)

def prior(path,build,mode,pattern):
    m=json.loads((path/'manifest.json').read_text());r=json.loads((path/'report.json').read_text());raw=(path/'output.bin').read_bytes()
    need(m['mode']==mode and m['pattern']==pattern and m['exit_code']==0 and m['GPU_reservation']['state']=='terminal' and
         not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and m['system_before']==m['system_after']==SYSTEM and
         m['original_binary_sha256']==sha(build/'host') and
         (mode=='baseline' or m['build_sha256']==sha(build/'build.json')) and m['signed_binary_sha256']==sha(path/'application'), 'prior process differs')
    args=m['arguments'];need(len(args)==7 and args[1]==mode and args[6]==str(pattern) and
        sha(Path(args[2]))==PINS['shader.metallib'] and sha(Path(args[3]))=='f99b8ca94aec90088ba8aee80c42b9e242a7829a81c3fedbf34b2312b08bacbe' and
        sha(Path(args[4]))==PINS['original.sass'] and
        sha(Path(args[5]))==(PINS['original.sass'] if mode=='baseline' else sha(build/'trace.sass')),'prior inputs differ')
    need(subprocess.run(['codesign','--verify','--strict',str(path/'application')],capture_output=True,timeout=15).returncode==0,'prior signature differs')
    return raw,r

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('lab','build','out'):p.add_argument('--'+key,type=Path,required=True)
    p.add_argument('--mode',choices=('trace',),required=True);p.add_argument('--pattern',type=int,choices=(0,2,3,4),required=True)
    p.add_argument('--baseline',type=Path);p.add_argument('--control-baseline',type=Path);p.add_argument('--control-trace',type=Path)
    a=p.parse_args();lab=a.lab.resolve();build=a.build.resolve();out=a.out.resolve()
    build.relative_to(lab/'results');out.relative_to(lab/'results');need(not out.exists() and out.parent.is_dir(),'fresh output required')
    profile=json.loads((build/'build.json').read_text())
    for name,digest in profile['files_SHA256'].items():need(sha(build/name)==digest,'build changed: '+name)
    need(sha(build/'shader.metallib')==PINS['shader.metallib'] and sha(build/'original.sass')==PINS['original.sass'] and
         sha(build/'native.metadata')=='f99b8ca94aec90088ba8aee80c42b9e242a7829a81c3fedbf34b2312b08bacbe' and
         sha(build/'trace.sass')=={0x298:'9bd7ad3485beba2bc3b4a9eb7fc43e514ecbe0b8613b7fc81c8ad0a659fe4227',0x2b8:'24c90474d293c99f1fe7fe4013397d9a1b76867730834e55c1477351441bb46b',0x330:'b80ec4b85bccfb3a621d220a462b41636228ffc26a82b6de539679f2a4bf7604'}.get(profile['target']),'profile or witness differs')
    for name in ('branch_witness_host.mm','cb0_readback_import.mm'):need(sha(build/name)==sha(HERE/name),'host source differs')
    need(sha(build/'KeplerNativeCAS.mm')==sha(BRIDGE/'src/KeplerNativeCAS.mm') and
         sha(build/'src/KeplerConditionalAux.h')==sha(BRIDGE/'src/KeplerConditionalAux.h') and
         sha(build/'src/KeplerNativeCASAdapter.inc')==sha(BRIDGE/'src/KeplerNativeCASAdapter.inc'),'runtime source differs')
    decoder=lab/'build/envydis-only/envydis/envydis'
    need(verify_decoder((build/'trace.sass').read_bytes(),(build/'trace.asm').read_text(),decoder),'decoder replay failed')
    baseline=None
    if a.mode=='trace':
        need(a.baseline is not None,'same-pattern baseline required');root=a.baseline.resolve();root.relative_to(lab/'results')
        baseline=prior(root,build,'baseline',a.pattern);verify_baseline(*baseline)
        if a.pattern!=0:
            need(a.control_baseline is not None and a.control_trace is not None,'pattern-0 control pair required')
            b=a.control_baseline.resolve();t=a.control_trace.resolve();b.relative_to(lab/'results');t.relative_to(lab/'results')
            br=prior(b,build,'baseline',0);tr=prior(t,build,'trace',0);need(compare(*br,*tr)['status']=='PASS','control differs')
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
        lease.spawning(binary,sha(binary));registry=lab/'results/signed-native-jobs.json';jobs=json.loads(registry.read_text()) if registry.exists() else []
        replacement=build/('original.sass' if a.mode=='baseline' else 'trace.sass')
        args=[str(out),a.mode,str(build/'shader.metallib'),str(build/'native.metadata'),str(build/'original.sass'),str(replacement),str(a.pattern)]
        env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','LD_','KM_CAS_'))}
        with (out/'report.json').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
            child=subprocess.Popen([str(binary),*args],stdout=stdout,stderr=stderr,pass_fds=(lease.fd,),env=env)
            lease.bind_child(child.pid);job={'started_at':now(),'pid':child.pid,'original_executable':str(build/'host'),
                'original_binary_sha256':profile['files_SHA256']['host'],'signed_executable':str(binary),
                'signed_binary_sha256':sha(binary),'arguments':args}
            jobs.append(job);registry.write_text(json.dumps(jobs,indent=2)+'\n')
            print(json.dumps({'status':'STARTED','pid':child.pid,'mode':a.mode,'pattern':a.pattern}),flush=True);code=child.wait()
        ps=subprocess.run(['ps','-p',str(child.pid),'-o','pid=,lstart=,command='],capture_output=True,text=True,timeout=10)
        need(ps.returncode in (0,1) and not ps.stderr,'process status unavailable');state=ps.stdout.strip()
        job.update(exit_code=code,SIGKILL_requested=False,authoritative_ps_status=state,completed_at=now())
        registry.write_text(json.dumps(jobs,indent=2)+'\n');lease.finish(code,False,state)
        after={path:sha(path) for path in SYSTEM}
        (out/'manifest.json').write_text(json.dumps({**job,'mode':a.mode,'pattern':a.pattern,'GPU_reservation':dict(lease.data),
             'system_before':before,'system_after':after,'target':profile['target'],'build_sha256':sha(build/'build.json')},indent=2)+'\n')
        need(code==0 and not state and before==after,'witness failed or profile changed')
        for name,digest in profile['files_SHA256'].items():need(sha(build/name)==digest,'build changed: '+name)
        r=json.loads((out/'report.json').read_text());proof=r['import'];events=proof['events']
        need(proof['contract_verified'] and proof['constructor_restored'] and len(events)==1 and
             events[0]['conditional_auxiliary_section_pinned'] and events[0]['expected_original_code_identical'] and
             events[0]['native_metadata_identical_to_certificate'] and events[0]['imported_code_identical'],'import evidence differs')
        raw=(out/'output.bin').read_bytes()
        result=compare(*baseline,raw,r) if baseline else {'status':'PASS','rows':len(verify_baseline(raw,r))}
        (out/'verified.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
        print(json.dumps({'status':'TERMINAL','mode':a.mode,'pattern':a.pattern,'result':result}),flush=True)
    except BaseException:
        if child is not None and child.poll() is None:lease.finish(None,False,'child outcome not established')
        raise
    finally:lease.close()

if __name__=='__main__':main()
