#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit one calibration and three serialized large/purge Metal-buffer pairs."""
import argparse, datetime, json, subprocess
from pathlib import Path
from verify_video_metal_resource_observer import read, sha, verify


def audit(paths):
    paths=[Path(x).resolve() for x in paths]
    modes=['control','large','purge','large','purge','large','purge']
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
        events=r['events']; opens=[x for x in events if x['kind']=='open' and x['status']==0 and x['type_or_selector']==6 and x['service_registry_ID']==i['registry_id']]
        if len(opens)!=1: raise ValueError('Shared client open not observed exactly once')
        port=opens[0]['port'];calls=[x for x in events if x['kind']=='method' and x['port']==port]
        creates=[x for x in calls if x['type_or_selector']==0 and x['status']==0 and x['input_scalar_count']==0 and x['input_struct_bytes']==168 and Path(x['caller_image']).name=='IOAccelerator' and x['caller_symbol']=='IOAccelResourceCreate']
        if not any(x['phase']==2 for x in creates) or not any(x['phase']==4 for x in creates): raise ValueError('Warmup or target creation not observed')
        row={'mode':i['mode'],'events':len(events),'target_length':r['target_length'],'target_weak_cleared':r['target_weak_cleared'],
             'resource_creations_during_target':sum(x['phase']==4 for x in creates),
             'shared_selector1_observed':sum(x['type_or_selector']==1 for x in calls),
             'all_intercepted_events_during_purge':sum(x['phase'] in (9,10,11,12,13,14) for x in events),
             'result_SHA256':sha(p/'results.json'),'manifest_SHA256':sha(p/'execution/manifest.json')}
        if i['mode']=='purge':
            states=[r[k] for k in ('state_initial','previous_empty','state_empty','previous_restore','state_restored')]
            if r['purge_exception'] or states!=[2,2,4,4,2] or not r['cpu_after_purge_checked'] or not r['cpu_after_purge_correct']:
                raise ValueError('Purge sequence or restored CPU access did not match the bounded oracle')
            row['state_sequence']=states;row['restored_cpu_bytes_correct']=True
        observations.append(row)
    return {'audit':'PASS','observations':observations,'separate_processes':len(items),'control_events':items[0][1]['event_count'],
            'build_inputs_SHA256':items[0][2]['build_inputs_SHA256'],'observer_SHA256':items[0][2]['observer_SHA256'],
            'phase_measures':'completion, not entry','event_coverage_complete':False,'physical_memory_reclaimed_proved':False,
            'resource_deletion_absence_proved':False,'resource_id_correlation_proved':False,'GPU_execution_proved':False,'video_execution_proved':False}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('results',nargs=7);a=p.parse_args();print(json.dumps(audit(a.results),indent=2,sort_keys=True))
