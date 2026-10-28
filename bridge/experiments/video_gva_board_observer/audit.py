#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck the signed board-observer cohort without running native code."""
import argparse,hashlib,json,subprocess
from datetime import datetime
from pathlib import Path
HERE=Path(__file__).resolve().parent

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(x,msg):
 if not x:raise ValueError(msg)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--hosts',type=Path,nargs=11,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();b=a.build.resolve();dirs=[x.resolve() for x in a.hosts];need(len(set(dirs))==11 and not a.out.exists() and a.out.parent.is_dir(),'fresh output and 11 distinct hosts required');i=read(b/'inputs.json')
 for n,h in i['frozen'].items():need(sha(b/n)==h,'Build changed: '+n)
 for n in ('observer.mm','calibrate.mm','experiment.py'):need(sha(HERE/n)==i['frozen'][n],'Source changed: '+n)
 need(i['old_registry_ID']==4294968458 and i['new_registry_ID']==4294968416 and i['driver_SHA256']=='44f131a958d48afd6ab675a851330c37506557c9d499484170c886c3731bdbb3','Profile differs')
 old=Path(i['base_build']);need(sha(old/'inputs.json')==i['base_inputs_SHA256'] and sha(old/'application')==i['base_executable_SHA256'],'Historical base differs');base=read(old/'inputs.json');oldlib=[Path(n) for n in base['reused_objects_and_libraries_SHA256'] if Path(n).name=='libVideoDependency-both.dylib'];need(len(oldlib)==1 and sha(oldlib[0])==i['old_dependency_SHA256'],'Original dependency differs');need(sha(oldlib[0].parent/'video_dependency.h')==i['frozen']['video_dependency.h'],'Dependency header differs');original=(oldlib[0].parent/'video_dependency.mm').read_text();need(original.count('4294968458')==12 and original.count('4294968459')==1 and (b/'video_dependency.mm').read_text()==original.replace('4294968458','4294968416').replace('4294968459','4294968417'),'Dependency source is not the ID-only change');profile=read(b/'assets/dependency-profile.json');oldprofile=read(old/'assets/dependency-profile.json');need(profile=={**oldprofile,'GPU_registry_ID':4294968416},'Dependency profile changed beyond ID');config=read(b/'assets/dependency-config.json');need(config['libraries']['both']==i['frozen']['libDependency.dylib'] and config['profile_SHA256']==i['frozen']['assets/dependency-profile.json'],'Dependency config differs')
 for name in ('libObserver.dylib','libDependency.dylib'):subprocess.run(['codesign','--verify','--strict',str(b/name)],check=True,capture_output=True)

 names=[('calibration',0),('inspect',0),('cpu',0),('native',0),('wrong',0),('current',1),('plain',1),('current',2),('plain',2),('current',3),('plain',3)];rows=[];intervals=[];pids=set()
 for d,(mode,_) in zip(dirs,names):
  m=read(d/'execution/manifest.json');l=m['GPU_reservation'];need(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and l['state']=='terminal' and l['child_PID']==m['pid'] and l['exit_code']==0 and not l['known_signed_processes_live'],'Unresolved process');need(m['pid'] not in pids,'Repeated pid');pids.add(m['pid']);intervals.append((datetime.fromisoformat(m['started_at']),datetime.fromisoformat(m['completed_at'])))
  app='calibrate' if mode=='calibration' else 'application';need(sha(d/'application')==m['original_binary_sha256']==i['frozen'][app] and sha(d/'execution/application')==m['signed_binary_sha256']==l['signed_binary_sha256'],'Application identity differs');subprocess.run(['codesign','--verify','--strict',str(d/'execution/application')],check=True,capture_output=True)
  injected=mode!='plain';need(m['injected_library_SHA256']==(i['frozen']['libObserver.dylib'] if injected else None),'Observer identity differs');need(m['launcher_SHA256']==i['frozen']['runtime/observer_run_host.py'] and m['reservation_module_SHA256']==i['frozen']['runtime/lab_gpu_reservation.py'],'Runner identity differs')
  for name,h in i['frozen'].items():
   if not name.startswith('assets/') or name in ('assets/owned-choice.json','assets/dependency-choice.json','assets/factory-policy-choice.json'):continue
   need(sha(d/name)==h,'Asset differs: '+name)
  if mode!='calibration':
   route='owned' if mode in ('cpu','native','wrong','current','plain') else 'native';override='present-key' if mode in ('wrong','current','plain') else 'native';policy='wrong-board' if mode=='wrong' else 'current-board' if mode in ('current','plain') else 'observe';expected_mode='hardware' if mode in ('native','wrong','current','plain') else mode
   need(read(d/'assets/owned-choice.json')=={'route':route} and read(d/'assets/dependency-choice.json')=={'mode':override} and read(d/'assets/factory-policy-choice.json')=={'mode':policy} and m['arguments']==[str(d/'assets'),str(d/'outputs'),expected_mode],'Actual choices or arguments differ')
  else:need(m['arguments']==[],'Calibration arguments differ')
  trace=(d/'execution/execution.stderr').read_text();board=[x for x in trace.splitlines() if x.startswith('KM_BOARD mode=gva ')];s=read(d/'summary.json');need(s['status']=='PASS','Recorded summary differs')
  if mode=='calibration':need('CALIBRATION_PASS' in (d/'execution/execution.stdout').read_text() and 'KM_BOARD mode=calibration profile=0 type=1 valid=1 selection=0 value=Mac-CALIBRATION' in trace and not board,'Calibration differs')
  elif mode=='inspect':need(not board,'Inspect should not produce GVA board event')
  else:
   result=read(d/'execution/execution.stdout');f=read(d/'outputs/factory-resolver.json');dep=read(d/'outputs/dependency.json');need(f['status']=='COMPLETE' and f['synthetic_controls_valid'] and dep['status']=='COMPLETE' and dep['recorders_drained'] and not dep['dropped'] and not dep['pending'] and dep['public_query_controls_valid'],'Observer controls differ');v=result['public_decode'];status=v['decode']['create_status'];frames=v['output_frames']
   if mode=='cpu':
    need(status==0 and frames==6 and v['different_bytes']==0 and v['CPU_reference_bytes_compared']==691200 and not board,'CPU control differs');total=0
    for k in range(6):
     actual=(d/'outputs'/f'vt-frame-{k:03d}.nv12').read_bytes();expected=(d/'assets/fixtures/H264'/f'cpu-frame-{k:03d}.nv12').read_bytes();need(actual==expected and len(actual)==115200,'CPU reference differs');total+=len(actual)
    need(total==691200,'CPU byte count differs')
   else:
    need(frames==0 and v['decode']['specification']['RequireHardwareAcceleratedVideoDecoder'] is True,'Hardware specification or frame count differs');need(status==(-12913 if mode in ('current','plain') else -12906),'Hardware status differs')
    need(dep['substitutions']==(0 if mode=='native' else 1),'Dependency substitution differs');need(f['policy_substitutions']==(3 if mode in ('current','plain') else 1 if mode=='wrong' else 0),'Policy substitution differs');need(f['pool_calls']==(1 if mode in ('current','plain') else 0),'Pool observation differs')
    if mode=='current':need(board==['KM_BOARD mode=gva profile=1 type=1 valid=1 selection=0 value=Mac-F2268DAE'] and f['GVA_stage_code_pins_valid'],'GVA board evidence differs')
    else:need(not board,'Unexpected board event')
   rows.append({'mode':mode,'create_status':status,'frames':frames,'board_events':len(board),'pool_calls':f['pool_calls']})
 intervals.sort();need(all(x<=y for x,y in intervals) and all(x[1]<=y[0] for x,y in zip(intervals,intervals[1:])),'processes overlap')
 result={'status':'PASS','terminal_nonoverlapping_processes':11,'injected_current_board_runs':3,'plain_current_board_runs':3,'observed_GVA_board_reads':3,'board_value_matches_iMac':True,'selection_ancestor_observed':False,'hardware_required_failures':8,'hardware_images':0,'software_images':6,'software_CPU_reference_bytes':691200,'observer_SHA256':i['frozen']['libObserver.dylib'],'revised_dependency_SHA256':i['frozen']['libDependency.dylib'],'original_registry_ID':i['old_registry_ID'],'current_registry_ID':i['new_registry_ID'],'driver_SHA256':i['driver_SHA256'],'scope':'Own process; pinned CFData caller and loaded code; conditional selection cause and hardware decoding remain unknown.'}
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
