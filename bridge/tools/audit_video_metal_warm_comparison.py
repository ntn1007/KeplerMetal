#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline comparison of one calibrated observer and two warm allocation cohorts."""
import argparse, datetime, json, subprocess
from pathlib import Path
from verify_video_metal_resource_observer import read, sha, verify


def audit(paths):
    paths=[Path(x).resolve() for x in paths]
    modes=['control','baseline','warmed','large','baseline','warmed','large']
    if len(paths)!=len(modes) or len(set(paths))!=len(modes): raise ValueError('Seven distinct result directories required')
    items=[]
    for p,mode in zip(paths,modes):
        v=verify(p); i=read(p/'inputs.json'); r=read(p/'results.json'); m=read(p/'execution/manifest.json')
        if v['mode']!=mode or read(p/'verification-execution.json')['exit_code']!=0: raise ValueError('Wrong mode or failed original oracle')
        subprocess.run(['codesign','--verify','--strict',str(p/'execution/application')],check=True,capture_output=True,timeout=15)
        subprocess.run(['codesign','--verify','--strict',str(p/'libResourceObserver.dylib')],check=True,capture_output=True,timeout=15)
        items.append((p,v,i,r,m))
    if len({x[2]['build_inputs_SHA256'] for x in items})!=1: raise ValueError('Different builds')
    if len({x[4]['pid'] for x in items})!=len(items): raise ValueError('Processes must be distinct')
    if len({(x[1]['gpu_registry_id'],x[1]['pci_registry_ID']) for x in items})!=1: raise ValueError('Different target GPU')
    if any(datetime.datetime.fromisoformat(a[4]['completed_at']) >= datetime.datetime.fromisoformat(b[4]['started_at']) for a,b in zip(items,items[1:])): raise ValueError('Runs overlapped or out of order')
    observations=[]
    for p,v,i,r,m in items[1:]:
        e=r['events']; opens=[x for x in e if x['kind']=='open' and x['status']==0 and x['type_or_selector']==6 and x['service_registry_ID']==i['registry_id']]
        if len(opens)!=1: raise ValueError('Shared client open not observed exactly once')
        port=opens[0]['port']
        creates=[x for x in e if x['kind']=='method' and x['port']==port and x['type_or_selector']==0 and x['status']==0 and x['input_scalar_count']==0 and x['input_struct_bytes']==168 and Path(x['caller_image']).name=='IOAccelerator' and x['caller_symbol']=='IOAccelResourceCreate']
        if not any(x['phase']==2 for x in creates): raise ValueError('No warmup creation observed')
        deletes=[x for x in e if x['kind']=='method' and x['port']==port and x['type_or_selector']==1]
        observations.append({'mode':i['mode'],'events':len(e),'target_length':r['target_length'],'warm_weak_cleared':r['warm_weak_cleared'],'target_weak_cleared':r['target_weak_cleared'],
                             'create_phase_2':sum(x['phase']==2 for x in creates),'create_phase_4':sum(x['phase']==4 for x in creates),
                             'create_other_phases':sum(x['phase'] not in (2,4) for x in creates),'delete_calls_observed':len(deletes),
                             'result_SHA256':sha(p/'results.json'),'manifest_SHA256':sha(p/'execution/manifest.json')})
    return {'audit':'PASS','control_events':items[0][1]['event_count'],'separate_processes':len(items),'observations':observations,
            'build_inputs_SHA256':items[0][2]['build_inputs_SHA256'],'observer_SHA256':items[0][2]['observer_SHA256'],
            'phase_measures':'completion, not entry','event_coverage_complete':False,'resource_id_correlation_proved':False,
            'resource_deletion_absence_proved':False,'scalar_and_payload_values_recorded':False,'GPU_execution_proved':False,'video_execution_proved':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('results',nargs=7);a=p.parse_args();print(json.dumps(audit(a.results),indent=2,sort_keys=True))
