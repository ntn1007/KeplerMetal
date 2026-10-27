#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit retained own-process Metal resource-identity observations."""
import argparse, copy, hashlib, json, subprocess, sys
from datetime import datetime
from pathlib import Path
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'video_context_object'))
from audit import result_check as device_check, manifest_check

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text())
def need(ok, reason):
    if not ok: raise ValueError(reason)

def result_check(r, rid):
    device_check(r, 'observe', rid)
    x = r['resource_identity']
    need(x == {'status': 'PINNED', 'slot_read': True, 'resource_nonnull': True,
               'getter_called': False, 'ivar_offset': 24,
               'negative_null_rejected': True, 'resource_shared_matches': True,
               'resource_slot_offset': 136,
               'getter_sha256': '348a6081407e4ff380a668ae3d6d4f67087965110af9380e090f87f83cd4d982'},
         'Resource identity or refusal')

def audit(build, runs):
    need(len(runs) == len(set(runs)) == 2, 'Two distinct hosts required')
    i = load(build/'inputs.json')
    for n,h in i['frozen'].items(): need(sha(build/n) == h, 'Frozen input '+n)
    for n in ('host.mm','observer.mm','experiment.py'): need(sha(HERE/n) == i['frozen']['src/'+n], 'Source changed '+n)
    need(sha(build/'application') == i['application_SHA256'] and sha(build/'libObjectObserver.dylib') == i['observer_SHA256'], 'Build artifacts')
    for n in ('application','libObjectObserver.dylib'):
        subprocess.run(['codesign','--verify','--strict',str(build/n)],capture_output=True,check=True,timeout=20)
    pids=set(); intervals=[]; rows=[]; samples=[]
    for p in runs:
        inp=load(p/'inputs.json');m=load(p/'execution/manifest.json');r=load(p/'result.json');rid=inp['registry_id']
        need(inp['mode']=='observe' and inp['build_inputs_SHA256']==sha(build/'inputs.json') and inp['profile']==i['profile'] and inp['observer_SHA256']==i['observer_SHA256'] and inp['application_SHA256']==i['application_SHA256'], 'Run provenance')
        need(sha(p/'application')==sha(p/'execution/application')==i['application_SHA256'] and load(p/'execution/execution.stdout')==r and str(build/'libObjectObserver.dylib') in m['dependency_listing'], 'Host artifact')
        need(sha(p/'runtime/run_sdk_host.py')==i['frozen']['runtime/run_sdk_host.py']==m['launcher_SHA256'] and sha(p/'runtime/lab_gpu_reservation.py')==i['frozen']['runtime/lab_gpu_reservation.py']==m['reservation_module_SHA256'], 'Runner changed')
        manifest_check(m,'observe',rid,i['application_SHA256']);result_check(r,rid)
        need(r['pid']==m['pid'] and m['pid'] not in pids,'PID mismatch');pids.add(m['pid'])
        intervals.append((datetime.fromisoformat(m['started_at']),datetime.fromisoformat(m['completed_at'])))
        samples.append((r,m,rid));rows.append({'pid':m['pid'],'result_SHA256':sha(p/'result.json'),'manifest_SHA256':sha(p/'execution/manifest.json')})
    intervals.sort();need(all(a<=b for a,b in intervals) and intervals[0][1]<=intervals[1][0], 'Overlapping hosts')
    r,m,rid=samples[0]; rejected=[]
    for key,value in [('resource_shared_matches',False),('resource_nonnull',False),('negative_null_rejected',False),('getter_called',True),('getter_sha256','0'*64),('resource_slot_offset',128)]:
        altered=copy.deepcopy(r);altered['resource_identity'][key]=value
        try: result_check(altered,rid)
        except ValueError: rejected.append(key)
        else: raise ValueError('Mutation accepted: '+key)
    altered=copy.deepcopy(m);altered['GPU_reservation']['state']='active'
    try: manifest_check(altered,'observe',rid,i['application_SHA256'])
    except ValueError: rejected.append('reservation_not_terminal')
    else: raise ValueError('Mutation accepted: reservation')
    return {'status':'PASS','hosts':2,'nonoverlapping':True,'application_SHA256':i['application_SHA256'],'observer_SHA256':i['observer_SHA256'],'shared_link_matches':2,'negative_null_rejected':2,'audit_mutations_rejected':rejected,'rows':rows,'explicit_GPU_dispatches':0,'hardware_video_execution_proved':False,'limits':['Pointer association does not qualify the resource as a video data buffer or establish its use by a video context.','No GPU execution or resource finalization is established.','A cooperative reservation does not exclude WindowServer or unrelated processes.','The observation covers this exact executable, getter, runtime and allocation profile.']}

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--runs',type=Path,nargs=2,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    need(not a.out.exists() and a.out.parent.is_dir(),'Fresh output required')
    result=audit(a.build.resolve(),[x.resolve() for x in a.runs])
    with a.out.open('x') as f: json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='rows'}))
if __name__=='__main__': main()
