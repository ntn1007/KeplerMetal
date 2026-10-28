#!/usr/bin/env python3
"""Build/run scoped GVA register observer using the existing no-kill lab lease."""
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
sys.path.insert(0,str(BRIDGE/'experiments/cas_divergence'))
from run_repair import SYSTEM
SYSTEM=dict(SYSTEM)
SYSTEM['/System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce']='44f131a958d48afd6ab675a851330c37506557c9d499484170c886c3731bdbb3'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,why):
    if not ok:raise ValueError(why)
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def command(argv):
    r=subprocess.run([str(x) for x in argv],capture_output=True,text=True,timeout=120)
    need(r.returncode==0,str(argv[0])+' failed: '+r.stderr[-1500:]);return r
def identity():
    r=command(['ioreg','-a','-r','-c','nvAccelerator','-d1']);v=plistlib.loads(r.stdout.encode())
    need(len(v)==1 and v[0]['IORegistryEntryName']=='nvAccelerator','accelerator identity differs')
    return v[0]['IORegistryEntryID']
def build(a):
    lab=a.lab.resolve();out=a.out.resolve();old=a.base.resolve()
    for p in (out,old):p.relative_to(lab/'results')
    need(not out.exists() and out.parent.is_dir(),'fresh output required')
    oldm=json.loads((old/'inputs.json').read_text())
    need(oldm['new_registry_ID']==identity() and oldm['driver_SHA256']==SYSTEM['/System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce'], 'old target differs')
    need({p:sha(p) for p in SYSTEM}==SYSTEM,'system profile differs')
    for name,digest in oldm['frozen'].items():need(sha(old/name)==digest,'old input differs: '+name)
    out.mkdir()
    for name in ('witness.h','tail.S','gva_observer.mm'):
        shutil.copyfile(HERE/name,out/name)
    dylib=out/'gva-register-observer.dylib'
    command(['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-Wall','-Wextra','-Werror','-dynamiclib',
             out/'tail.S',out/'gva_observer.mm','-framework','Foundation','-o',dylib])
    command(['codesign','--force','--sign','-',dylib]);command(['codesign','--verify','--strict',dylib])
    frozen={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'build.json').write_text(json.dumps({'status':'PREPARED','frozen':frozen,'base_inputs_sha256':sha(old/'inputs.json'),
         'base_application_sha256':oldm['frozen']['application'],'base_observer_sha256':oldm['frozen']['libObserver.dylib'],
         'registry_id':oldm['new_registry_ID'],'system':SYSTEM,'GPU_execution':False},indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':'PREPARED','observer_sha256':sha(dylib),'GPU_execution':False}),flush=True)

def run(a):
    lab,old,build,out=(getattr(a,k).resolve() for k in ('lab','base','build','out'))
    for p in (old,build,out):p.relative_to(lab/'results')
    need(not out.exists() and out.parent.is_dir(),'fresh run path required')
    m=json.loads((build/'build.json').read_text());oldm=json.loads((old/'inputs.json').read_text())
    need(m['base_inputs_sha256']==sha(old/'inputs.json') and m['registry_id']==identity() and
         m['system']==SYSTEM and {p:sha(p) for p in SYSTEM}==SYSTEM,'profile differs')
    for name,digest in m['frozen'].items():need(sha(build/name)==digest,'new build differs: '+name)
    for name,digest in oldm['frozen'].items():need(sha(old/name)==digest,'base differs: '+name)
    for name in ('witness.h','tail.S','gva_observer.mm'):need(sha(build/name)==sha(HERE/name),'observer source differs: '+name)
    lease_module=lab/'results/video-rm-access-build-20261018-03/runtime/lab_gpu_reservation.py'
    need(sha(lease_module)=='ee637d27c5af482b1fbce396f6a49ef234b09a7d8602aeb36edc422f46b61248','lease differs')
    spec=importlib.util.spec_from_file_location('lab_gpu_reservation',lease_module);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    lease=module.GPUReservation(lab);child=None
    try:
        out.mkdir();shutil.copytree(old/'assets',out/'assets');(out/'outputs').mkdir()
        mode=a.mode
        def choice(name,value):(out/'assets'/name).write_text(json.dumps({'mode':value},indent=2)+'\n')
        (out/'assets/owned-choice.json').write_text(json.dumps({'route':'owned'},indent=2)+'\n')
        choice('dependency-choice.json','native' if mode=='cpu' else 'present-key')
        choice('factory-policy-choice.json','observe' if mode=='cpu' else 'wrong-board' if mode=='wrong' else 'current-board')
        env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','LD_','KM_'))}
        env['DYLD_INSERT_LIBRARIES']=(str(build/'gva-register-observer.dylib')+':' if a.witness=='on' else '')+str(old/'libObserver.dylib')
        env['KM_BOARD_MODE']='observe';env['KM_GVA_POLICY']='none'
        exe=out/'application';shutil.copyfile(old/'application',exe);exe.chmod(0o755)
        need(sha(exe)==m['base_application_sha256'],'host differs')
        for p in (exe,build/'gva-register-observer.dylib',old/'libObserver.dylib'):command(['codesign','--verify','--strict',p])
        args=[str(out/'assets'),str(out/'outputs'),'cpu' if mode=='cpu' else 'hardware']
        lease.spawning(exe,sha(exe));registry=lab/'results/signed-native-jobs.json';jobs=json.loads(registry.read_text()) if registry.exists() else []
        with (out/'stdout.json').open('wb') as stdout,(out/'stderr.log').open('wb') as stderr:
            child=subprocess.Popen([str(exe),*args],stdout=stdout,stderr=stderr,pass_fds=(lease.fd,),env=env);lease.bind_child(child.pid)
            job={'started_at':now(),'pid':child.pid,'original_executable':str(old/'application'),'original_binary_sha256':sha(old/'application'),
                 'signed_executable':str(exe),'signed_binary_sha256':sha(exe),'arguments':args}
            jobs.append(job);registry.write_text(json.dumps(jobs,indent=2)+'\n')
            print(json.dumps({'status':'STARTED','pid':child.pid,'mode':mode}),flush=True);code=child.wait()
        proc=subprocess.run(['ps','-p',str(child.pid),'-o','pid=,lstart=,command='],capture_output=True,text=True,timeout=10)
        need(proc.returncode in (0,1) and not proc.stderr,'process status unavailable');state=proc.stdout.strip()
        job.update(exit_code=code,SIGKILL_requested=False,authoritative_ps_status=state,completed_at=now())
        registry.write_text(json.dumps(jobs,indent=2)+'\n');lease.finish(code,False,state)
        after={p:sha(p) for p in SYSTEM}
        manifest={**job,'mode':mode,'witness':a.witness,'GPU_reservation':dict(lease.data),'system_before':SYSTEM,'system_after':after,
                  'observer_sha256':sha(build/'gva-register-observer.dylib') if a.witness=='on' else None,'base_observer_sha256':sha(old/'libObserver.dylib'),
                  'build_sha256':sha(build/'build.json'),'base_inputs_sha256':sha(old/'inputs.json')}
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2,sort_keys=True)+'\n')
        need(code==0 and not state and after==SYSTEM,'process failed or profile changed')
        for name,digest in m['frozen'].items():need(sha(build/name)==digest,'observer changed: '+name)
        for name,digest in oldm['frozen'].items():need(sha(old/name)==digest,'base changed: '+name)
        report=json.loads((out/'stdout.json').read_text());need(report['status']=='OBSERVATION_COMPLETED','host result differs')
        lines=[x for x in (out/'stderr.log').read_text().splitlines() if x.startswith('KM_GVA_REGISTER ')]
        need(len(lines)==(1 if a.witness=='on' else 0),'observer final status differs')
        print(json.dumps({'status':'TERMINAL','mode':mode,'witness':a.witness,'observer':lines[0] if lines else None,
                          'decoder_status':report['public_decode']['decode']['create_status'],
                          'output_frames':report['public_decode']['output_frames']}),flush=True)
    except BaseException:
        if child is not None and child.poll() is None:lease.finish(None,False,'child outcome not established')
        raise
    finally:lease.close()

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);subs=p.add_subparsers(required=True)
    for name in ('build','run'):
        q=subs.add_parser(name)
        for key in (('lab','base','out') if name=='build' else ('lab','base','build','out')):q.add_argument('--'+key,type=Path,required=True)
        if name=='run':
            q.add_argument('--mode',choices=('cpu','wrong','current'),required=True)
            q.add_argument('--witness',choices=('on','off'),default='on')
        q.set_defaults(func=build if name=='build' else run)
    args=p.parse_args();args.func(args)
