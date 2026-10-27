#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify a bounded video context/shared-client association witness offline."""
from pathlib import Path
import hashlib,json,sys

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def verify(path):
    p=Path(path).resolve();i=read(p/'inputs.json');r=read(p/'results.json');m=read(p/'execution/manifest.json');lease=m['GPU_reservation'];mode=i['mode']
    assert mode in ('inventory','wrong-target','pair','attach')
    assert r==read(p/'execution/execution.stdout') and m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
    assert lease['state']=='terminal' and lease['exit_code']==0 and lease['child_PID']==m['pid'] and not lease['known_signed_processes_live']
    assert r['pid']==m['pid'] and r['uid']==r['euid']==i['user_UID']!=0
    assert sha(p/'application')==i['executable_SHA256']==m['original_binary_sha256']
    assert sha(p/'execution/application')==m['signed_binary_sha256']==lease['signed_binary_sha256']
    for name,digest in i['frozen'].items():assert sha(p/name)==digest,name
    assert m['launcher_SHA256']==i['frozen']['runtime/run_sdk_host.py'] and m['reservation_module_SHA256']==i['frozen']['runtime/lab_gpu_reservation.py']
    expected='pair' if mode=='wrong-target' else mode
    assert m['arguments']==[expected,str(i['registry_id'])] and r['mode']==expected and r['target']==i['registry_id']
    assert not r['matching_status'] and not r['truncated'] and not r['explicit_selector_calls'] and not r['explicit_GPU_commands'] and not r['hardware_video_execution_proved']
    devs=[v for v in r['services'] if v['class']=='nvAccelerator' and v['gpu_ancestor'] and not v['class_status'] and not v['registry_status']]
    assert len(devs)==1 and devs[0]['pci_registry_ID']
    if mode in ('inventory','wrong-target'):
        assert not r['candidate_count'] and not r['metal_enumeration_attempted'] and not r['context_open_attempts'] and not r['shared_open_attempts'] and not r['association_attempts']
        assert not r['context_returned'] and not r['shared_returned'] and not r['context_close_attempts'] and not r['shared_close_attempts']
        assert r['status']==('INVENTORY_ONLY' if mode=='inventory' else 'TARGET_NOT_QUALIFIED')
        if mode=='wrong-target':assert i['registry_id']==1
        outcome='CONTROL_PASS'
    else:
        assert r['candidate_count']==1 and devs[0]['candidate'] and i['registry_id']==devs[0]['registry_ID']
        assert r['pci_registry_ID']==devs[0]['pci_registry_ID']==r['metal_pci_registry_ID']
        assert r['metal_enumeration_attempted'] and r['metal_candidates']==1 and r['metal_registry_ID']
        assert r['context_open_attempts']==r['shared_open_attempts']==1 and r['context_open_status']==r['shared_open_status']==0
        assert r['context_returned'] and r['shared_returned'] and r['handles_distinct']
        assert r['context_close_attempts']==r['shared_close_attempts']==1 and r['context_close_status']==r['shared_close_status']==0
        if mode=='pair':
            assert r['status']=='PAIR_OPEN' and not r['association_attempts'];outcome='PAIR_OPEN_CLOSED'
        else:
            assert r['association_attempts']==1
            if r['association_status']==0:assert r['status']=='ASSOCIATION_ACCEPTED';outcome='ASSOCIATION_ACCEPTED'
            else:assert r['status']=='ASSOCIATION_REFUSED';outcome='ASSOCIATION_REFUSED'
    return {'verification':'PASS','outcome':outcome,'mode':mode,'gpu_registry_id':devs[0]['registry_ID'],
            'pci_registry_ID':devs[0]['pci_registry_ID'],'metal_registry_ID':r['metal_registry_ID'],
            'association_status_hex':hex(r['association_status'] & 0xffffffff) if r['association_attempts'] else None,
            'explicit_selector_calls':0,'explicit_GPU_commands':0,'driver_internal_activity_traced':False,
            'hardware_video_execution_proved':False}

if __name__=='__main__':print(json.dumps(verify(sys.argv[1]),sort_keys=True))
