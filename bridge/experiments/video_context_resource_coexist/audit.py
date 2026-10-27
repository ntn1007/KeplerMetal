#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify simultaneous native context and Metal resource observations."""
import argparse, copy, hashlib, json, subprocess, sys
from collections import Counter
from datetime import datetime
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'video_context_object'))
from audit import manifest_check

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def need(ok,reason):
    if not ok: raise ValueError(reason)

def check(r,mode,rid):
    need(r['mode']==mode and r['registry_id']==rid and r['status']=='OBSERVATION_COMPLETED' and r['metal_candidates']==1 and r['buffer_CPU_correct'] and r['buffer_CPU_after_context_correct'] and r['explicit_GPU_dispatches']==0 and not r['hardware_video_execution_proved'],'Host and CPU checks')
    a=r['resource_identity'];x=r['observation']
    need(a['status']=='PINNED' and a['slot_read'] and a['resource_nonnull'] and a['resource_shared_matches'] and a['resource_shared_after'] and a['negative_null_rejected'] and a['null_context_rejected'] and not a['getter_called'] and a['ivar_offset']==24 and a['resource_slot_offset']==136 and a['getter_sha256']=='348a6081407e4ff380a668ae3d6d4f67087965110af9380e090f87f83cd4d982','Resource observations')
    need(x['create_calls']==x['matching_nonnull']==x['matching_type']==1 and x['shared_calls']==x['shared_matching_argument']==x['shared_nonnull']==x['shared_type_matches']==x['shared_stored_device_matches']==1 and x['return_unchanged'] and x['registry_query_failures']==x['type_or_profile_failures']==x['shared_failures']==x['config_calls']==x['config_failures']==0,'Device and shared checks')
    if mode=='observe':
        need(not a['context_requested'] and not a['context_started'] and x['context_attempts']==x['resource_while_context_matches']==x['probe_open_calls']==x['probe_add_calls']==x['probe_release_calls']==0,'Observe control')
    else:
        need(mode=='coexist' and a['context_requested'] and a['context_started'] and x['context_attempts']==x['context_type_matches']==x['context_shared_matches']==x['context_connection_matches']==x['resource_while_context_matches']==1 and x['context_slots']==16 and x['context_slots_empty']==1 and x['probe_guards_calibrated']==1,'Coexistence checks')
        need(x['probe_open_calls']==x['probe_add_calls']==x['probe_release_calls']==1 and x['probe_open_status']==x['probe_add_status']==x['probe_release_status']==0 and x['probe_denied_selectors']==x['probe_unexpected']==0,'Context operations')

def audit(build, runs):
    need(len(runs)==len(set(runs))==4,'Four distinct hosts required');i=read(build/'inputs.json')
    for n,h in i['frozen'].items():need(sha(build/n)==h,'Frozen input '+n)
    for n in ('host.mm','observer.mm','experiment.py'):need(sha(HERE/n)==i['frozen']['src/'+n],'Source changed '+n)
    need(sha(build/'application')==i['application_SHA256'] and sha(build/'libObjectObserver.dylib')==i['observer_SHA256'],'Build artifacts')
    for n in ('application','libObjectObserver.dylib'):subprocess.run(['codesign','--verify','--strict',str(build/n)],capture_output=True,check=True,timeout=20)
    pids=set();intervals=[];modes=[];rows=[];samples=[]
    for p in runs:
        inp=read(p/'inputs.json');m=read(p/'execution/manifest.json');r=read(p/'result.json');mode=inp['mode'];rid=inp['registry_id']
        need(inp['build_inputs_SHA256']==sha(build/'inputs.json') and inp['profile']==i['profile'] and inp['observer_SHA256']==i['observer_SHA256'] and inp['application_SHA256']==i['application_SHA256'],'Run provenance')
        need(sha(p/'application')==sha(p/'execution/application')==i['application_SHA256'] and read(p/'execution/execution.stdout')==r and str(build/'libObjectObserver.dylib') in m['dependency_listing'],'Host artifact')
        need(sha(p/'runtime/run_sdk_host.py')==i['frozen']['runtime/run_sdk_host.py']==m['launcher_SHA256'] and sha(p/'runtime/lab_gpu_reservation.py')==i['frozen']['runtime/lab_gpu_reservation.py']==m['reservation_module_SHA256'],'Runner changed')
        manifest_check(m,mode,rid,i['application_SHA256']);check(r,mode,rid)
        need(r['pid']==m['pid'] and m['pid'] not in pids,'PID mismatch');pids.add(m['pid']);modes.append(mode)
        intervals.append((datetime.fromisoformat(m['started_at']),datetime.fromisoformat(m['completed_at'])));samples.append((r,m,rid))
        rows.append({'mode':mode,'pid':m['pid'],'result_SHA256':sha(p/'result.json'),'manifest_SHA256':sha(p/'execution/manifest.json')})
    intervals.sort();need(Counter(modes)==Counter({'observe':2,'coexist':2}) and all(a<=b for a,b in intervals) and all(a[1]<=b[0] for a,b in zip(intervals,intervals[1:])),'Modes or overlap')
    r,m,rid=next(v for v in samples if v[0]['mode']=='coexist');rejected=[]
    for section,key,val in [('resource_identity','resource_shared_after',False),('resource_identity','null_context_rejected',False),('observation','resource_while_context_matches',0),('observation','context_slots_empty',0),('observation','probe_add_status',1),('observation','probe_denied_selectors',1),(None,'buffer_CPU_after_context_correct',False)]:
        x=copy.deepcopy(r);(x[section] if section else x)[key]=val
        try:check(x,'coexist',rid)
        except ValueError:rejected.append(key)
        else:raise ValueError('Mutation accepted '+key)
    bad=copy.deepcopy(m);bad['GPU_reservation']['state']='active'
    try:manifest_check(bad,'coexist',rid,i['application_SHA256'])
    except ValueError:rejected.append('reservation_not_terminal')
    else:raise ValueError('Mutation accepted reservation')
    return {'status':'PASS','hosts':4,'controls':2,'coexistence_hosts':2,'buffer_bytes_checked_before_and_after_per_host':4194304,'nonoverlapping':True,'application_SHA256':i['application_SHA256'],'observer_SHA256':i['observer_SHA256'],'audit_mutations_rejected':rejected,'rows':rows,'explicit_GPU_dispatches':0,'hardware_video_execution_proved':False,'limits':['The context is empty: the Metal buffer is not bound as a video data buffer.','Pointer association does not establish complete resource lifetime or cleanup.','No GPU computation or hardware video decoding is demonstrated.','Reservation and guarded imports do not cover unrelated processes or all driver activity.']}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--runs',type=Path,nargs=4,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'Fresh output required')
    r=audit(a.build.resolve(),[x.resolve() for x in a.runs])
    with a.out.open('x') as f:json.dump(r,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({k:v for k,v in r.items() if k!='rows'}))
if __name__=='__main__':main()
