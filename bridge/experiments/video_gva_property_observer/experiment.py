#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build a process-local board observer with an explicitly checked new registry ID."""
import argparse,hashlib,json,os,plistlib,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1];sys.path.insert(0,str(BRIDGE/'tools'))
from native_video_factory import verify_owned
from dependency_patch import apply as extend_dependency
from public_large_scratch import sha,write
DRIVER='/System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce'
DRIVER_SHA='44f131a958d48afd6ab675a851330c37506557c9d499484170c886c3731bdbb3'
OLD_ID=4294968458;OLD_WRONG=4294968459

def replace_json(path,value):
 Path(path).write_text(json.dumps(value,indent=2)+'\n')
def need(x,msg):
 if not x:raise ValueError(msg)
def current_id():
 p=subprocess.run(['ioreg','-a','-r','-c','nvAccelerator','-d1'],check=True,capture_output=True,timeout=20);v=plistlib.loads(p.stdout);need(len(v)==1 and v[0]['IORegistryEntryName']=='nvAccelerator','Accelerator identity ambiguous');return v[0]['IORegistryEntryID']
def command(label,argv,out):
 r=subprocess.run(list(map(str,argv)),capture_output=True,text=True,timeout=90);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);need(r.returncode==0,label+' failed');print(label+' PASS',flush=True)
def build(a):
 old=a.base.resolve();out=a.out.resolve();need(not out.exists() and out.parent.is_dir(),'fresh output required');need(current_id()==a.accel_id and sha(DRIVER)==DRIVER_SHA,'Current accelerator or driver profile differs')
 d=json.loads((old/'inputs.json').read_text());parent=Path(d['owned_build']);need(sha(parent/'inputs.json')==d['owned_inputs_SHA256'],'Parent changed');verify_owned(parent)
 for folder,key in [('', 'source_hashes'),('assets','assets_SHA256'),('runtime','runtime_SHA256')]:
  for n,h in d[key].items():need(sha(old/folder/n)==h,'Base input changed: '+n)
 for n,h in d['reused_objects_and_libraries_SHA256'].items():need(sha(n)==h,'Base dependency changed')
 need(sha(old/'application')==d['executable_SHA256'] and sha(old/'libVideoFactoryResolver.dylib')==d['resolver_library_SHA256'],'Base binary changed')
 oldlibs=[Path(x) for x in d['reused_objects_and_libraries_SHA256'] if Path(x).name=='libVideoDependency-both.dylib'];need(len(oldlibs)==1,'Old dependency not unique')
 source=BRIDGE/'tools/video_dependency.mm';source_old=oldlibs[0].parent/'video_dependency.mm';need(sha(source)==sha(source_old),'Dependency source differs');src=source.read_text();need(src.count(str(OLD_ID))==12 and src.count(str(OLD_WRONG))==1 and a.accel_id!=OLD_ID,'Unexpected old registry ID references')
 out.mkdir();shutil.copytree(old/'assets',out/'assets');shutil.copytree(old/'runtime',out/'runtime');shutil.copyfile(BRIDGE/'tools/video_dependency.h',out/'video_dependency.h');shutil.copyfile(HERE/'observer.mm',out/'observer.mm');shutil.copyfile(HERE/'calibrate.mm',out/'calibrate.mm');shutil.copyfile(HERE/'experiment.py',out/'experiment.py');shutil.copyfile(HERE/'dependency_patch.py',out/'dependency_patch.py');shutil.copyfile(BRIDGE/'experiments/standalone_icb/run_host.py',out/'runtime/observer_run_host.py');(out/'video_dependency.mm').write_text(extend_dependency(src.replace(str(OLD_ID),str(a.accel_id)).replace(str(OLD_WRONG),str(a.accel_id+1))))
 profile=json.loads((out/'assets/dependency-profile.json').read_text());need(profile['GPU_registry_ID']==OLD_ID,'Old profile differs');profile['GPU_registry_ID']=a.accel_id;replace_json(out/'assets/dependency-profile.json',profile)
 common=['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-Wno-deprecated-declarations'];frameworks=['-framework','Foundation','-framework','CoreMedia','-framework','VideoToolbox','-framework','CoreVideo','-framework','Metal','-framework','IOKit'];candidate=out/'libDependency.dylib';observer=out/'libObserver.dylib'
 command('dependency',common+['-dynamiclib','-DKPDEP_RECORD=1','-DKPDEP_ENABLE=1',out/'video_dependency.mm',*frameworks,'-install_name',candidate,'-o',candidate],out);command('sign-dependency',['codesign','--force','--sign','-',candidate],out)
 cfg=json.loads((out/'assets/dependency-config.json').read_text());need(cfg['libraries']['both']==sha(oldlibs[0]),'Old library identity differs');cfg['libraries']['both']=sha(candidate);cfg['profile_SHA256']=sha(out/'assets/dependency-profile.json');replace_json(out/'assets/dependency-config.json',cfg)
 command('observer',common+['-dynamiclib',out/'observer.mm','-framework','Foundation','-framework','Metal','-framework','CoreFoundation','-framework','IOKit','-o',observer],out);command('sign-observer',['codesign','--force','--sign','-',observer],out);command('calibration',common+[out/'calibrate.mm','-framework','Foundation','-framework','Metal','-framework','CoreFoundation','-framework','IOKit','-o',out/'calibrate'],out);command('sign-calibration',['codesign','--force','--sign','-',out/'calibrate'],out)
 shutil.copyfile(old/'application',out/'application');command('replace-own-link',['install_name_tool','-change',oldlibs[0],candidate,out/'application'],out);command('sign-application',['codesign','--force','--sign','-',out/'application'],out)
 listing=subprocess.run(['otool','-L',str(out/'application')],check=True,capture_output=True,text=True).stdout;need(str(candidate) in listing and str(oldlibs[0]) not in listing,'New dependency link differs')
 frozen={str(p.relative_to(out)):sha(p) for directory in ('assets','runtime') for p in (out/directory).rglob('*') if p.is_file()};frozen.update({name:sha(out/name) for name in ('observer.mm','calibrate.mm','experiment.py','dependency_patch.py','video_dependency.h','video_dependency.mm','libDependency.dylib','libObserver.dylib','calibrate','application')});write(out/'inputs.json',{'frozen':frozen,'base_build':str(old),'base_inputs_SHA256':sha(old/'inputs.json'),'base_executable_SHA256':d['executable_SHA256'],'old_dependency_SHA256':sha(oldlibs[0]),'old_registry_ID':OLD_ID,'new_registry_ID':a.accel_id,'driver_SHA256':DRIVER_SHA,'profile_change':'Explicit local registry ID only; original system and older artifacts unchanged','native_executed_during_build':False});print('BUILD PASS',flush=True)
def run(a):
 b=a.build.resolve();out=a.out.resolve();i=json.loads((b/'inputs.json').read_text());need(not out.exists() and out.parent.is_dir(),'fresh output required');need(current_id()==i['new_registry_ID'] and sha(DRIVER)==i['driver_SHA256'],'Current accelerator or driver differs');need(sha(Path(i['base_build'])/'inputs.json')==i['base_inputs_SHA256'],'Base inputs differ')
 for n,h in i['frozen'].items():need(sha(b/n)==h,'Frozen input differs: '+n)
 need(sha(HERE/'experiment.py')==i['frozen']['experiment.py'],'Runner source changed');out.mkdir();shutil.copytree(b/'assets',out/'assets');(out/'outputs').mkdir();mode=a.mode
 if mode!='calibration':
  route='owned' if mode in ('cpu','native','wrong','current','patched','no-offline') else 'native';override='present-key' if mode in ('wrong','current','patched','no-offline') else 'native';policy='wrong-board' if mode=='wrong' else 'current-board' if mode in ('current','patched','no-offline') else 'observe'
  replace_json(out/'assets/owned-choice.json',{'route':route});replace_json(out/'assets/dependency-choice.json',{'mode':override});replace_json(out/'assets/factory-policy-choice.json',{'mode':policy})
  args=[str(out/'assets'),str(out/'outputs'),'hardware' if mode in ('native','wrong','current','patched','no-offline') else mode];exe=b/'application'
 else:args=[];exe=b/'calibrate'
 shutil.copyfile(exe,out/'application');(out/'application').chmod(0o755);env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','KM_BOARD_'))};env['DYLD_INSERT_LIBRARIES']=str(b/'libObserver.dylib');env['KM_BOARD_MODE']='calibration' if mode=='calibration' else 'observe';env['KM_GVA_POLICY']='board-no-offline' if mode=='no-offline' else 'board' if mode=='patched' else 'none'
 sys.path.insert(0,str(b/'runtime'));from observer_run_host import run_host
 manifest=run_host(out/'application',out/'execution',args,a.reservation_root.resolve(),child_env=env);trace=(out/'execution/execution.stderr').read_text();stdout=(out/'execution/execution.stdout').read_text();rows=[x for x in trace.splitlines() if x.startswith('KM_BOARD ')];need(not any('profile=0' in x for x in rows if 'mode=gva' in x) and 'KM_GVA_DEP profile_refused' not in trace and not any('profile=0' in x for x in trace.splitlines() if x.startswith('KM_GVA_LOOKUP mode=gva ')) and not any('profile=0' in x for x in trace.splitlines() if x.startswith('KM_DEVICES mode=gva ')) and not any('profile=0' in x for x in trace.splitlines() if x.startswith('KM_PATH ') and 'offset=0 ' not in x) and not any('profile=0' in x for x in trace.splitlines() if x.startswith('KM_PROPERTY ') and 'offset=0 ' not in x) and 'KM_ITERATOR dropped=1' not in trace and not any('profile=0' in x for x in trace.splitlines() if x.startswith('KM_ITERATOR ') and 'offset=0 ' not in x),'GVA profile mismatch')
 if mode=='calibration':need('CALIBRATION_PASS' in stdout and any('mode=calibration' in x and 'valid=1 selection=0 value=Mac-CALIBRATION' in x for x in rows) and 'KM_GVA_LOOKUP mode=calibration profile=0 offset=0 valid=1 original=1 present=1 changed=0 key=KM-LOOKUP-CALIBRATION' in trace and 'KM_ITERATOR kind=create offset=0 profile=0 status=0 present=1' in trace and 'KM_ITERATOR kind=next offset=0 profile=0 status=0 present=1' in trace and 'KM_DEVICES mode=calibration profile=0 valid=1' in trace and 'KM_PATH kind=boolean offset=0 profile=0 result=1' in trace and 'KM_PATH kind=release offset=0 profile=0 result=0' in trace and any(x.startswith('KM_PROPERTY offset=0 profile=0 ') and 'key=IOKitBuildVersion' in x and 'present=1' in x for x in trace.splitlines()),'Calibration failed')
 else:
  result=json.loads(stdout);need(json.loads((out/'outputs/factory-resolver.json').read_text())['status']=='COMPLETE','Factory observer incomplete');(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
  if mode=='cpu':need(result['public_decode']['different_bytes']==0 and result['public_decode']['output_frames']>0,'Software control differs')
  if mode in ('native','wrong','current'):need(result['public_decode']['output_frames']==0,'Unexpected image; inspect before new run')
 summary={'status':'PASS','mode':mode,'pid':manifest['pid'],'registry_ID':i['new_registry_ID'],'GVA_board_events':len([r for r in rows if 'mode=gva' in r]),'board_events':rows,'injected_SHA256':manifest['injected_library_SHA256'],'exit_code':manifest['exit_code'],'hardware_decode_proved':False,'source_uses_old_GPU_registry_ID':False};write(out/'summary.json',summary);print(json.dumps(summary),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(required=True);b=s.add_parser('build');b.add_argument('--base',type=Path,required=True);b.add_argument('--out',type=Path,required=True);b.add_argument('--accel-id',type=int,required=True);b.set_defaults(fn=build);r=s.add_parser('run');r.add_argument('--build',type=Path,required=True);r.add_argument('--out',type=Path,required=True);r.add_argument('--reservation-root',type=Path,required=True);r.add_argument('--mode',choices=('calibration','inspect','cpu','native','wrong','current','patched','no-offline'),required=True);r.set_defaults(fn=run);a=p.parse_args();a.fn(a)
