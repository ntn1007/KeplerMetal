#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build and serialize public VideoToolbox tests with a process-local observer."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

HERE=Path(__file__).resolve().parent
BRIDGE=HERE.parents[1]
sys.path.insert(0,str(HERE.parent/'video_bsp_staging'))
sys.path.insert(0,str(HERE.parent/'cas_divergence'))
from validate_baseline import EXPECTED
from run_repair import SYSTEM
REFERENCE='d73962c0592ae107d343591bf2d72e013015813e3b2ceff71d37e2c5fee36cd1'
RESERVATION='ee637d27c5af482b1fbce396f6a49ef234b09a7d8602aeb36edc422f46b61248'
SOURCE={'client.mm':HERE/'client.mm','observer.mm':HERE/'observer.mm','lldb_witness.py':HERE/'lldb_witness.py','lldb_guard.py':HERE/'lldb_guard.py'}
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def need(ok,message):
    if not ok: raise ValueError(message)
def command(args):
    p=subprocess.run(list(map(str,args)),capture_output=True,timeout=120)
    need(p.returncode==0,str(args[0])+' failed: '+p.stderr.decode(errors='replace')[-2000:])
    return p.stdout.decode()
def profile():
    current={path:sha(path) for path in SYSTEM}
    need(current==SYSTEM,'system profile differs'); return current
def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='action',required=True)
    b=sub.add_parser('build'); r=sub.add_parser('run')
    for parser in (b,r):
        parser.add_argument('--lab',type=Path,required=True); parser.add_argument('--out',type=Path,required=True)
    b.add_argument('--calibration',type=Path,required=True); b.add_argument('--fixture',type=Path,required=True); b.add_argument('--reference',type=Path,required=True)
    r.add_argument('--build',type=Path,required=True); r.add_argument('--mode',choices=('software-plain','software-observed','hardware-plain','hardware-observed','metal-plain','metal-observed'),required=True)
    a=p.parse_args(); lab=a.lab.resolve(); out=a.out.resolve(); out.relative_to(lab/'results')
    need(not out.exists() and out.parent.is_dir(),'fresh output required')
    if a.action=='build':
        cal=json.loads((a.calibration/'calibration.json').read_text()); need(cal['status']=='PASS_CPU_ENUMERATION_WITNESS' and cal['wrong_target_rejected'] and cal['null_result_verified'] and cal['allocation_identity_verified'] and cal['equal_and_different_verified'] and cal['sources']['lldb_witness.py']==sha(HERE/'lldb_witness.py') and cal['sources']['lldb_guard.py']==sha(HERE/'lldb_guard.py'),'calibration differs')
        state=profile(); need({f.name:sha(f) for f in a.fixture.iterdir() if f.is_file()}==EXPECTED and sha(a.reference)==REFERENCE,'fixture differs')
        out.mkdir(); (out/'fixture').mkdir()
        for name,path in SOURCE.items(): shutil.copyfile(path,out/name)
        for name in EXPECTED: shutil.copyfile(a.fixture/name,out/'fixture'/name)
        shutil.copyfile(a.reference,out/'reference.nv12')
        sdk=command(['xcrun','--show-sdk-path']).strip()
        command(['xcrun','clang++','-arch','x86_64','-std=c++17','-O2','-fobjc-arc','-dynamiclib',out/'observer.mm',
                 '-F'+sdk+'/System/Library/PrivateFrameworks','-framework','IOAccelerator','-framework','Foundation','-framework','IOKit','-framework','Metal','-o',out/'observer.dylib'])
        command(['xcrun','clang++','-arch','x86_64','-std=c++17','-Wall','-Wextra','-Werror','-O1','-g','-fobjc-arc',out/'client.mm',
            '-framework','Foundation','-framework','VideoToolbox','-framework','CoreVideo','-framework','CoreMedia','-framework','IOKit','-framework','Metal','-o',out/'client'])
        ent=out/'entitlements.plist'; ent.write_bytes(plistlib.dumps({'com.apple.security.get-task-allow':True}))
        command(['codesign','--force','--sign','-',out/'observer.dylib']); command(['codesign','--force','--sign','-','--entitlements',ent,out/'client'])
        for name in ('observer.dylib','client'): command(['codesign','--verify','--strict',out/name])
        need(profile()==state,'system changed during build')
        record={'status':'PREPARED','system':state,'fixture':EXPECTED,'reference':REFERENCE,
            'source_sha256':{n:sha(path) for n,path in SOURCE.items()},
            'build_sha256':{n:sha(out/n) for n in ('client','observer.dylib')},
            'builder_sha256':sha(Path(__file__)),'calibration_sha256':sha(a.calibration/'calibration.json'),'gpu_execution':False}
        (out/'build.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
        print(json.dumps({'status':'PREPARED','gpu_execution':False})); return
    build=a.build.resolve(); build.relative_to(lab/'results'); data=json.loads((build/'build.json').read_text()); profile()
    need(data['status']=='PREPARED' and data['system']==SYSTEM and data['builder_sha256']==sha(Path(__file__)) and
         data['source_sha256']=={n:sha(path) for n,path in SOURCE.items()} and
         data['build_sha256']=={n:sha(build/n) for n in ('client','observer.dylib')} and
         data['fixture']=={n:sha(build/'fixture'/n) for n in EXPECTED} and sha(build/'reference.nv12')==REFERENCE,'build differs')
    leasepath=lab/'results/video-rm-access-build-20261018-03/runtime/lab_gpu_reservation.py'
    need(sha(leasepath)==RESERVATION,'reservation differs'); spec=importlib.util.spec_from_file_location('imac_vt_reservation',leasepath)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); lease=mod.GPUReservation(lab)
    child=None; finished=False
    try:
        out.mkdir();
        for name in ('client','observer.dylib'):
            shutil.copyfile(build/name,out/name); need(sha(out/name)==data['build_sha256'][name],'copy differs'); command(['codesign','--verify','--strict',out/name])
        host=out/'client'; host.chmod(0o755); library=out/'observer.dylib'; mode=a.mode.split('-')[0]
        env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','LD_','KM_','KP_'))}
        if a.mode.endswith('observed'): env['DYLD_INSERT_LIBRARIES']=str(library)
        lease.spawning(host,sha(host)); started=datetime.datetime.now(datetime.timezone.utc).isoformat()
        with (out/'stdout.json').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
            child=subprocess.Popen([str(host),str(build/'fixture'),str(out/'decoded.nv12'),mode],stdout=stdout,stderr=stderr,
                                   pass_fds=(lease.fd,),env=env)
            lease.bind_child(child.pid); print(json.dumps({'status':'STARTED','pid':child.pid}),flush=True); code=child.wait()
        alive=mod.process_table().get(child.pid); lease.finish(code,False,'' if alive is None else 'child still visible')
        finished=True; need(not alive and code==0,'host failed or still visible')
        need(profile()==SYSTEM and data['build_sha256']=={n:sha(build/n) for n in ('client','observer.dylib')} and
             all(sha(out/n)==data['build_sha256'][n] for n in ('client','observer.dylib')),'profile/binary changed')
        result=json.loads((out/'stdout.json').read_text()); need(result['mode']==mode and result['observer_loaded']==a.mode.endswith('observed') and
            (isinstance(result['observation'],dict) if a.mode.endswith('observed') else result['observation'] is None),'client or observer differs')
        if result['status']=='PASS': need(sha(out/'decoded.nv12')==REFERENCE,'decoded pixels differ')
        elif result['status']=='METAL_PASS': need(mode=='metal' and not (out/'decoded.nv12').exists(),'unexpected Metal path')
        else: need(result['status']=='CREATE_FAILED' and not (out/'decoded.nv12').exists(),'unexpected failed path')
        manifest={'status':'TERMINAL','mode':a.mode,'pid':child.pid,'exit_code':code,'started_at':started,
            'completed_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reservation':dict(lease.data),
            'build_sha256':sha(build/'build.json'),'stdout_sha256':sha(out/'stdout.json'),'stderr_sha256':sha(out/'stderr.log'),
            'host_sha256':sha(host),'observer_sha256':sha(library),'system_before':SYSTEM,'system_after':SYSTEM,
            'runner_sha256':sha(Path(__file__)),'system_modified':False}
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        print(json.dumps({'status':'TERMINAL','create_status':result['create_status'],'result':result['status']}),flush=True)
    finally:
        if not finished: lease.finish(0 if child is None else None,False,'' if child is None else 'child terminal outcome not established')
        lease.close()
if __name__=='__main__': main()
