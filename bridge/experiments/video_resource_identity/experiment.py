#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Observe an object naturally returned to an ordinary Metal client."""
import argparse,json,os,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'tools'))
from public_large_scratch import commands,preflight,sha,read,write
from video_metal_resource_observer import check_profile
def need(v,s):
 if not v:raise ValueError(s)
def build(a):
 out=a.out.resolve();preflight(out);profile=check_profile();out.mkdir();(out/'src').mkdir();(out/'runtime').mkdir()
 for n in ('host.mm','observer.mm','experiment.py'):shutil.copyfile(HERE/n,out/'src'/n)
 shutil.copyfile(BRIDGE/'sdk-combined/runtime/run_sdk_host.py',out/'runtime/run_sdk_host.py');shutil.copyfile(BRIDGE/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py')
 run=commands(out);sdk=subprocess.check_output(['xcrun','--show-sdk-path'],text=True).strip();lib=out/'libObjectObserver.dylib';common=['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc']
 run('observer',common+['-dynamiclib',out/'src/observer.mm','-F'+sdk+'/System/Library/PrivateFrameworks','-framework','IOAccelerator','-framework','Foundation','-framework','IOKit','-install_name',lib,'-o',lib]);run('sign-observer',['codesign','--force','--sign','-',lib]);run('verify-observer',['codesign','--verify','--strict',lib])
 run('host',common+[out/'src/host.mm',lib,'-framework','Foundation','-framework','IOKit','-framework','Metal','-o',out/'application']);run('sign-host',['codesign','--force','--sign','-',out/'application']);run('verify-host',['codesign','--verify','--strict',out/'application'])
 frozen={str(x.relative_to(out)):sha(x) for folder in ('src','runtime') for x in (out/folder).rglob('*') if x.is_file()}
 write(out/'inputs.json',{'profile':profile,'user_UID':os.getuid(),'frozen':frozen,'application_SHA256':sha(out/'application'),'observer_SHA256':sha(lib),'GPU_dispatches':0})
 print(json.dumps({'status':'BUILD_PASS','GPU_dispatches':0}))
def run(a):
 b=a.build.resolve();o=a.out.resolve();i=read(b/'inputs.json');need(not o.exists() and o.parent.is_dir() and (a.lab/'results').is_dir(),'Fresh lab result required')
 for n,h in i['frozen'].items():need(sha(b/n)==h,'Frozen input changed '+n)
 for n in ('host.mm','observer.mm','experiment.py'):need(sha(HERE/n)==i['frozen']['src/'+n],'Source changed '+n)
 need(sha(b/'application')==i['application_SHA256'] and sha(b/'libObjectObserver.dylib')==i['observer_SHA256'] and check_profile()==i['profile'] and os.getuid()==i['user_UID'],'Profile or build changed')
 o.mkdir();shutil.copyfile(b/'application',o/'application');(o/'application').chmod(0o755);shutil.copytree(b/'runtime',o/'runtime')
 write(o/'inputs.json',{'build_inputs_SHA256':sha(b/'inputs.json'),'registry_id':a.registry_id,'mode':a.mode,'profile':i['profile'],'application_SHA256':i['application_SHA256'],'observer_SHA256':i['observer_SHA256']})
 sys.path.insert(0,str(o/'runtime'));from run_sdk_host import run_host
 m=run_host(o/'application',o/'execution',[a.mode,str(a.registry_id)],a.lab.resolve());need(check_profile()==i['profile'] and sha(b/'libObjectObserver.dylib')==i['observer_SHA256'],'Profile changed during run')
 r=read(o/'execution/execution.stdout');need(r['pid']==m['pid'] and r['mode']==a.mode and r['registry_id']==a.registry_id and r['status']=='OBSERVATION_COMPLETED' and r['metal_candidates']==1 and r['buffer_CPU_correct'] and not r['hardware_video_execution_proved'],'Host result differs')
 write(o/'result.json',r);print(json.dumps({'status':'OBSERVED' if r['observation']['matching_nonnull'] else 'NOT_OBSERVED','observation':r['observation'],'hardware_video_execution_proved':False}))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);sp=p.add_subparsers(required=True);b=sp.add_parser('build');b.add_argument('--out',type=Path,required=True);b.set_defaults(func=build)
 r=sp.add_parser('run');r.add_argument('--build',type=Path,required=True);r.add_argument('--out',type=Path,required=True);r.add_argument('--lab',type=Path,required=True);r.add_argument('--registry-id',type=int,required=True);r.add_argument('--mode',choices=['observe','config','context'],required=True);r.set_defaults(func=run);a=p.parse_args();a.func(a)
