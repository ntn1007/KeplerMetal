#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify a bounded same-process Metal/shared-client observation offline."""
from pathlib import Path
import hashlib, json, sys

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def verify(path):
    p=Path(path).resolve();i=read(p/'inputs.json');r=read(p/'results.json');m=read(p/'execution/manifest.json');lease=m['GPU_reservation'];mode=i['mode']
    assert mode in ('inventory','wrong-target','direct','device','queue')
    assert r==read(p/'execution/execution.stdout') and m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
    assert lease['state']=='terminal' and lease['exit_code']==0 and lease['child_PID']==m['pid'] and not lease['known_signed_processes_live']
    assert r['pid']==m['pid'] and r['uid']==r['euid']==i['user_UID']!=0
    assert sha(p/'application')==i['executable_SHA256']==m['original_binary_sha256']
    assert sha(p/'execution/application')==m['signed_binary_sha256']==lease['signed_binary_sha256']
    for name,digest in i['frozen'].items():assert sha(p/name)==digest,name
    assert m['launcher_SHA256']==i['frozen']['runtime/run_sdk_host.py'] and m['reservation_module_SHA256']==i['frozen']['runtime/lab_gpu_reservation.py']
    expected='direct' if mode=='wrong-target' else mode
    assert m['arguments']==[expected,str(i['registry_id'])] and r['mode']==expected and r['target']==i['registry_id']
    assert not r['matching_status'] and not r['truncated'] and not r['explicit_IOConnect_calls'] and not r['explicit_GPU_commands'] and not r['hardware_video_execution_proved']
    devices=[v for v in r['services'] if v['class']=='nvAccelerator' and v['gpu_ancestor'] and not v['class_status'] and not v['registry_status']]
    assert len(devices)==1 and devices[0]['pci_registry_ID']
    if mode in ('inventory','wrong-target'):
        assert not r['candidate_count'] and not r['open_attempts'] and not r['close_attempts'] and not r['metal_enumeration_attempted']
        assert r['status']==('INVENTORY_ONLY' if mode=='inventory' else 'TARGET_NOT_QUALIFIED')
        if mode=='wrong-target':assert i['registry_id']==1
        outcome='CONTROL_PASS'
    else:
        assert r['candidate_count']==1 and devices[0]['candidate'] and i['registry_id']==devices[0]['registry_ID']
        assert r['pci_registry_ID']==devices[0]['pci_registry_ID'] and r['open_attempts']==1
        assert r['metal_enumeration_attempted']==(mode in ('device','queue'))
        assert r['queue_attempted']==r['queue_created']==(mode=='queue')
        if mode in ('device','queue'):assert r['metal_candidates']==1 and r['metal_registry_ID'] and r['metal_pci_registry_ID']==r['pci_registry_ID']
        else:assert not r['metal_candidates'] and not r['metal_registry_ID'] and not r['metal_pci_registry_ID']
        if r['status']=='OPEN_CLOSED':
            assert r['connection_returned'] and r['close_attempts']==1 and r['open_status']==r['close_status']==0
            outcome='OPEN_CLOSED'
        else:
            assert r['status']=='OPEN_REFUSED' and not r['connection_returned'] and not r['close_attempts'] and r['open_status']!=0
            outcome='OPEN_REFUSED'
    return {'verification':'PASS','outcome':outcome,'mode':mode,'gpu_registry_id':devices[0]['registry_ID'],
            'pci_registry_ID':devices[0]['pci_registry_ID'], 'metal_registry_ID':r['metal_registry_ID'], 'metal_pci_registry_ID':r['metal_pci_registry_ID'],
            'open_status_hex':hex(r['open_status'] & 0xffffffff) if r['open_attempts'] else None,
            'explicit_IOConnect_calls':0,'explicit_GPU_commands':0,'Metal_internal_activity_traced':False,
            'hardware_video_execution_proved':False}

if __name__=='__main__':print(json.dumps(verify(sys.argv[1]),sort_keys=True))
