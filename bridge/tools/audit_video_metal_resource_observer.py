#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit three retained process-local observations, without contacting a GPU."""
import argparse, datetime, json, subprocess
from pathlib import Path
from verify_video_metal_resource_observer import read, sha, verify


def audit(paths):
    paths=[Path(x).resolve() for x in paths]
    if len(set(paths))!=3: raise ValueError('Three distinct result directories required')
    items=[]
    for p in paths:
        v=verify(p); i=read(p/'inputs.json'); r=read(p/'results.json'); m=read(p/'execution/manifest.json')
        if read(p/'verification-execution.json')['exit_code']!=0: raise ValueError('Original oracle failed')
        subprocess.run(['codesign','--verify','--strict',str(p/'execution/application')],check=True,capture_output=True,timeout=15)
        subprocess.run(['codesign','--verify','--strict',str(p/'libResourceObserver.dylib')],check=True,capture_output=True,timeout=15)
        items.append((p,v,i,r,m))
    if [x[1]['mode'] for x in items]!=['control','buffer','buffer']: raise ValueError('Expected control, then two buffers')
    if len({x[2]['build_inputs_SHA256'] for x in items})!=1: raise ValueError('Different builds')
    if len({x[4]['pid'] for x in items})!=3: raise ValueError('Processes must be distinct')
    if len({(x[1]['gpu_registry_id'],x[1]['pci_registry_ID']) for x in items})!=1: raise ValueError('Different target GPU')
    if any(datetime.datetime.fromisoformat(a[4]['completed_at']) >= datetime.datetime.fromisoformat(b[4]['started_at']) for a,b in zip(items,items[1:])): raise ValueError('Runs overlapped or out of order')
    observations=[]
    for p,v,i,r,m in items[1:]:
        e=r['events']; opens=[x for x in e if x['kind']=='open' and x['status']==0 and x['type_or_selector']==6 and x['service_registry_ID']==i['registry_id']]
        if len(opens)!=1: raise ValueError('Shared client open not observed exactly once')
        port=opens[0]['port']
        creates=[x for x in e if x['kind']=='method' and x['port']==port and x['type_or_selector']==0 and x['status']==0 and x['input_scalar_count']==0 and x['input_struct_bytes']==168 and Path(x['caller_image']).name=='IOAccelerator' and x['caller_symbol']=='IOAccelResourceCreate']
        if not creates: raise ValueError('No matching resource create observed')
        deletes=[x for x in e if x['kind']=='method' and x['port']==port and x['type_or_selector']==1]
        observations.append({'events':len(e),'shared_opens':len(opens),'resource_create_calls_observed':len(creates),'resource_create_completion_phases':sorted(set(x['phase'] for x in creates)), 'selector_1_calls_observed':len(deletes),'result_SHA256':sha(p/'results.json'),'manifest_SHA256':sha(p/'execution/manifest.json')})
    return {'audit':'PASS','control_events':items[0][1]['event_count'],'separate_processes':3,'shared_create_observations':observations,
            'build_inputs_SHA256':items[0][2]['build_inputs_SHA256'],'observer_SHA256':items[0][2]['observer_SHA256'],
            'scalar_and_payload_values_recorded':False,'event_coverage_complete':False,'phase_measures':'completion, not entry',
            'resource_to_public_buffer_correlation_proved':False,'resource_deletion_absence_proved':False,'GPU_execution_proved':False,'video_execution_proved':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('control');p.add_argument('buffer1');p.add_argument('buffer2');a=p.parse_args();print(json.dumps(audit([a.control,a.buffer1,a.buffer2]),indent=2,sort_keys=True))
