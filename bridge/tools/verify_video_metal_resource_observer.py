#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify a scoped Metal resource observation; no driver calls are made here."""
from pathlib import Path
import hashlib,json,sys

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def verify(path):
    p=Path(path).resolve();i=read(p/'inputs.json');r=read(p/'results.json');m=read(p/'execution/manifest.json');lease=m['GPU_reservation'];mode=i['mode']
    assert mode in ('inventory','wrong-target','control','buffer','baseline','warmed','large')
    assert r==read(p/'execution/execution.stdout') and m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
    assert lease['state']=='terminal' and lease['exit_code']==0 and lease['child_PID']==m['pid'] and not lease['known_signed_processes_live']
    assert r['pid']==m['pid'] and r['uid']==r['euid']==i['user_UID']!=0
    assert sha(p/'application')==i['executable_SHA256']==m['original_binary_sha256']
    assert sha(p/'libResourceObserver.dylib')==i['observer_SHA256']
    assert i['observer_library'] in m['dependency_listing']
    assert sha(p/'execution/application')==m['signed_binary_sha256']==lease['signed_binary_sha256']
    for name,digest in i['frozen'].items():assert sha(p/name)==digest,name
    assert m['launcher_SHA256']==i['frozen']['runtime/run_sdk_host.py'] and m['reservation_module_SHA256']==i['frozen']['runtime/lab_gpu_reservation.py']
    expected='control' if mode=='wrong-target' else mode
    assert m['arguments']==[expected,str(i['registry_id'])] and r['mode']==expected and r['target']==i['registry_id']
    assert not r['matching_status'] and not r['truncated'] and not r['dropped'] and not r['observer_inflight_final']
    assert not r['scalar_values_recorded'] and not r['payload_bytes_recorded'] and not r['explicit_GPU_commands'] and not r['hardware_video_execution_proved']
    devices=[v for v in r['services'] if v['class']=='nvAccelerator' and v['gpu_ancestor'] and not v['class_status'] and not v['registry_status']]
    assert len(devices)==1 and devices[0]['pci_registry_ID']
    events=r['events'];assert len(events)<=2048
    if mode in ('inventory','wrong-target'):
        assert not r['candidate_count'] and not events and r['status']==('INVENTORY_ONLY' if mode=='inventory' else 'TARGET_NOT_QUALIFIED')
        if mode=='wrong-target':assert i['registry_id']==1
        outcome='CONTROL_PASS'
    else:
        assert r['candidate_count']==1 and devices[0]['candidate'] and i['registry_id']==devices[0]['registry_ID']
        assert r['pci_registry_ID']==devices[0]['pci_registry_ID']
        if mode=='control':
            assert r['status']=='CONTROL_RECORDED' and r['null_method_status']!=0 and r['null_struct_status']!=0
            for kind,status in [('method',r['null_method_status']),('struct',r['null_struct_status'])]:
                assert any(e['kind']==kind and e['port']==0 and e['status']==status & 0xffffffff for e in events),kind
            opens=[e for e in events if e['kind']=='open' and e['type_or_selector']==3 and e['service_registry_ID']==i['registry_id'] and e['status']==0]
            assert r['control_open_status']==r['control_close_status']==0 and r['control_connection'] and len(opens)==1
            assert any(e['kind']=='close' and e['port']==opens[0]['port'] and e['status']==0 for e in events)
            outcome='HOOK_CONTROLS_PASS'
        elif mode=='buffer':
            assert r['status']=='BUFFER_RELEASED' and r['metal_candidates']==1 and r['metal_registry_ID'] and r['metal_pci_registry_ID']==r['pci_registry_ID']
            assert r['buffer_created'] and r['cpu_bytes_correct'];outcome='BUFFER_CPU_PASS'
        else:
            assert r['status']=='WARM_COMPARISON_RECORDED' and r['metal_candidates']==1 and r['metal_registry_ID'] and r['metal_pci_registry_ID']==r['pci_registry_ID']
            assert r['warm_created'] and isinstance(r['warm_weak_cleared'],bool) and isinstance(r['target_weak_cleared'],bool)
            assert r['target_created']==(mode in ('warmed','large')) and r['cpu_bytes_correct']
            assert r['target_length']==(0 if mode=='baseline' else 4096 if mode=='warmed' else 4*1024*1024)
            if mode=='baseline':assert r['target_weak_cleared']
            outcome='WARM_COMPARISON_PASS'
    opens=[e for e in events if e['kind']=='open' and e['service_registry_ID']==devices[0]['registry_ID'] and e['status']==0 and e['type_or_selector']==6]
    shared_ports={e['port'] for e in opens if e['port']}
    calls=[e for e in events if e['kind']=='method' and e['port'] in shared_ports and e['type_or_selector']==1]
    return {'verification':'PASS','outcome':outcome,'mode':mode,'gpu_registry_id':devices[0]['registry_ID'],
            'pci_registry_ID':devices[0]['pci_registry_ID'],'event_count':len(events),'observed_shared_opens':len(opens),
            'observed_shared_selector1':len(calls),'observed_shared_selector1_success':sum(e['status']==0 for e in calls),
            'payload_values_recorded':False,'event_coverage_complete':False,'GPU_execution_proved':False}

if __name__=='__main__':print(json.dumps(verify(sys.argv[1]),sort_keys=True))
