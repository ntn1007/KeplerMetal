#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit a bounded own-process Metal device-object observation."""
import argparse,copy,hashlib,json,subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
HERE=Path(__file__).resolve().parent
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def need(v,s):
 if not v:raise ValueError(s)
def result_check(r,mode,rid):
 need(r['mode']==mode and r['registry_id']==rid and r['status']=='OBSERVATION_COMPLETED' and r['metal_candidates']==1 and r['buffer_CPU_correct'] and r['explicit_GPU_dispatches']==0 and not r['hardware_video_execution_proved'],'Metal result')
 x=r['observation'];need(x['create_calls']==x['matching_nonnull']==x['matching_type']==1 and x['return_unchanged'] and not x['registry_query_failures'] and not x['type_or_profile_failures'] and not x['config_failures'],'Object/type observation')
 if mode=='observe':need(x['config_calls']==0 and x['config_status']==-1 and x['config_values_match_object']==0,'No-config control')
 else:
  need(mode=='config' and x['config_calls']==1 and x['config_status']==0 and x['config_values_match_object']==1,'Config status')
  v=x['config_values'];need(len(v)==5 and all(type(i)==int and 0<=i<2**32 for i in v) and v==x['object_before']==x['object_after'],'Independent object/config values')
 return x

def manifest_check(m,mode,rid,appsha):
 lease=m['GPU_reservation'];need(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and m['arguments']==[mode,str(rid)] and lease['state']=='terminal' and lease['child_PID']==m['pid'] and not lease['known_signed_processes_live'] and lease['signed_binary_sha256']==m['signed_binary_sha256']==appsha and m['original_binary_sha256']==appsha,'Terminal host')
def audit(b,paths):
 need(len(paths)==len(set(paths))==4,'Four distinct hosts required');i=load(b/'inputs.json')
 for n,h in i['frozen'].items():need(sha(b/n)==h,'Frozen input '+n)
 for n in ('host.mm','observer.mm','experiment.py'):need(sha(HERE/n)==i['frozen']['src/'+n],'Source changed '+n)
 need(sha(b/'application')==i['application_SHA256'] and sha(b/'libObjectObserver.dylib')==i['observer_SHA256'],'Build artifact')
 for n in ('application','libObjectObserver.dylib'):subprocess.run(['codesign','--verify','--strict',str(b/n)],capture_output=True,check=True,timeout=20)
 intervals=[];pids=set();modes=[];config=[];rows=[];raw=[]
 for p in paths:
  inp=load(p/'inputs.json');m=load(p/'execution/manifest.json');r=load(p/'result.json');mode=inp['mode'];rid=inp['registry_id']
  need(inp['build_inputs_SHA256']==sha(b/'inputs.json') and inp['profile']==i['profile'] and inp['observer_SHA256']==i['observer_SHA256'] and inp['application_SHA256']==i['application_SHA256'],'Run provenance')
  need(sha(p/'application')==sha(p/'execution/application')==i['application_SHA256'] and load(p/'execution/execution.stdout')==r and str(b/'libObjectObserver.dylib') in m['dependency_listing'],'Host artifact')
  need(sha(p/'runtime/run_sdk_host.py')==i['frozen']['runtime/run_sdk_host.py']==m['launcher_SHA256'] and sha(p/'runtime/lab_gpu_reservation.py')==i['frozen']['runtime/lab_gpu_reservation.py']==m['reservation_module_SHA256'],'Runner changed')
  manifest_check(m,mode,rid,i['application_SHA256']);x=result_check(r,mode,rid)
  need(r['pid']==m['pid'] and m['pid'] not in pids,'PID mismatch');pids.add(m['pid']);intervals.append((datetime.fromisoformat(m['started_at']),datetime.fromisoformat(m['completed_at'])));modes.append(mode);raw.append((r,m,rid))
  if mode=='config':config.append(x['config_values'])
  rows.append({'mode':mode,'pid':m['pid'],'result_SHA256':sha(p/'result.json'),'manifest_SHA256':sha(p/'execution/manifest.json')})
 need(Counter(modes)==Counter({'observe':2,'config':2}) and len(config)==2 and config[0]==config[1],'Mode or repeat mismatch')
 intervals.sort();need(all(a<=b for a,b in intervals) and all(a[1]<=b[0] for a,b in zip(intervals,intervals[1:])),'Overlapping hosts')
 config_result=next(r for r,m,rid in raw if r['mode']=='config');control_result=next(r for r,m,rid in raw if r['mode']=='observe');rid=next(rid for r,m,rid in raw if r['mode']=='config');manifest=next(m for r,m,rid in raw if r['mode']=='config')
 corrupt=[]
 cases=[]
 a=copy.deepcopy(config_result);a['observation']['config_values'][0]^=1;cases.append(('changed-output',lambda:result_check(a,'config',rid)))
 a2=copy.deepcopy(config_result);a2['observation']['matching_type']=0;cases.append(('type-mismatch',lambda:result_check(a2,'config',rid)))
 a3=copy.deepcopy(control_result);a3['observation']['config_calls']=1;cases.append(('control-called-config',lambda:result_check(a3,'observe',rid)))
 a4=copy.deepcopy(manifest);a4['GPU_reservation']['state']='active';cases.append(('unterminated-reservation',lambda:manifest_check(a4,'config',rid,i['application_SHA256'])))
 for name,fn in cases:
  try:fn()
  except ValueError:corrupt.append(name)
  else:raise ValueError('Mutation accepted: '+name)
 return {'status':'PASS','hosts':len(rows),'nonoverlapping':True,'application_SHA256':i['application_SHA256'],'observer_SHA256':i['observer_SHA256'],'configuration_words':config[0],'config_repetitions':len(config),'negative_controls_rejected':corrupt,'rows':rows,'hardware_video_execution_proved':False,'actual_GPU_dispatches':0,'limits':['Configuration meanings are unknown; matching an object does not establish decoder compatibility.','The cooperative reservation does not exclude WindowServer or unrelated processes.','Only the two observed process-local calls are qualified; wider lifetime and concurrency remain untested.']}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--runs',type=Path,nargs=4,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'Fresh output required');r=audit(a.build.resolve(),[p.resolve() for p in a.runs]);
 with a.out.open('x') as f:json.dump(r,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps({k:v for k,v in r.items() if k!='rows'}))
if __name__=='__main__':main()
