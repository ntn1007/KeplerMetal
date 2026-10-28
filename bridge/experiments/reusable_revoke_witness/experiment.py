#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build and run one isolated, GPU-reserved revocation witness."""
import argparse,json,os,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'tools'))
from public_large_scratch import commands,preflight,sha,read,write
from video_metal_resource_observer import check_profile
def need(x,m):
 if not x:raise ValueError(m)
def build(a):
 out=a.out.resolve();preflight(out);profile=check_profile();out.mkdir();(out/'src').mkdir();(out/'runtime').mkdir()
 for n in ('host.mm','experiment.py'):shutil.copyfile(HERE/n,out/'src'/n)
 shutil.copyfile(BRIDGE/'src/KeplerReusableIRContext.inc',out/'src/KeplerReusableIRContext.inc')
 shutil.copyfile(BRIDGE/'sdk-combined/runtime/run_sdk_host.py',out/'runtime/run_sdk_host.py');shutil.copyfile(BRIDGE/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py')
 run=commands(out);run('host',['xcrun','clang++','-arch','x86_64','-std=c++17','-O2','-fobjc-arc',out/'src/host.mm','-framework','Foundation','-framework','IOKit','-framework','Metal','-o',out/'application']);run('sign',['codesign','--force','--sign','-',out/'application']);run('verify',['codesign','--verify','--strict',out/'application'])
 frozen={str(x.relative_to(out)):sha(x) for folder in ('src','runtime') for x in (out/folder).rglob('*') if x.is_file()}
 write(out/'inputs.json',{'profile':profile,'user_UID':os.getuid(),'frozen':frozen,'application_SHA256':sha(out/'application'),'GPU_dispatches':0});print(json.dumps({'status':'BUILD_PASS','GPU_dispatches':0}))
def run(a):
 b=a.build.resolve();o=a.out.resolve();i=read(b/'inputs.json');need(not o.exists() and o.parent.is_dir() and (a.lab/'results').is_dir(),'fresh lab result required')
 for n,h in i['frozen'].items():need(sha(b/n)==h,'frozen source changed '+n)
 for n in ('host.mm','experiment.py'):need(sha(HERE/n)==i['frozen']['src/'+n],'source changed '+n)
 need(sha(BRIDGE/'src/KeplerReusableIRContext.inc')==i['frozen']['src/KeplerReusableIRContext.inc'],'lease implementation changed')
 need(sha(b/'application')==i['application_SHA256'] and check_profile()==i['profile'] and os.getuid()==i['user_UID'],'profile/build changed')
 o.mkdir();shutil.copyfile(b/'application',o/'application');(o/'application').chmod(0o755);shutil.copytree(b/'runtime',o/'runtime')
 write(o/'inputs.json',{'build_inputs_SHA256':sha(b/'inputs.json'),'registry_id':a.registry_id,'mode':a.mode,'profile':i['profile'],'application_SHA256':i['application_SHA256']})
 sys.path.insert(0,str(o/'runtime'));from run_sdk_host import run_host
 m=run_host(o/'application',o/'execution',[a.mode,str(a.registry_id),str(o)],a.lab.resolve());need(check_profile()==i['profile'],'profile changed during run')
 r=read(o/'execution/execution.stdout');need(r['pid']==m['pid'] and r['mode']==a.mode and r['registry_id']==a.registry_id and r['device_candidates']==1 and r['completed'] and r['written'] and not r['system_modified'],'host result')
 write(o/'result.json',r);print(json.dumps({'status':'OBSERVED','mode':a.mode,'dispatches':r['dispatches'],'guard_installed':r['guard_installed']}))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);sp=p.add_subparsers(required=True);b=sp.add_parser('build');b.add_argument('--out',type=Path,required=True);b.set_defaults(func=build)
 r=sp.add_parser('run');r.add_argument('--build',type=Path,required=True);r.add_argument('--out',type=Path,required=True);r.add_argument('--lab',type=Path,required=True);r.add_argument('--registry-id',type=int,required=True);r.add_argument('--mode',choices=['native','revoked','revoked-negative'],required=True);r.set_defaults(func=run);a=p.parse_args();a.func(a)
