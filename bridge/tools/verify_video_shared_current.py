#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline witness oracle: no driver calls or profile changes."""
from pathlib import Path
import hashlib, json, sys

def read(p):return json.loads(p.read_text())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def verify(path, allow_refusal=False):
    p=Path(path).resolve();i=read(p/'inputs.json');r=read(p/'results.json');m=read(p/'execution/manifest.json');mode=i['mode'];lease=m['GPU_reservation']
    assert mode in ('inventory','wrong-target','shared') and r==read(p/'execution/execution.stdout')
    assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
    assert lease['state']=='terminal' and lease['exit_code']==0 and lease['child_PID']==m['pid'] and not lease['known_signed_processes_live']
    assert r['pid']==m['pid'] and r['uid']==r['euid']==i['user_UID']!=0
    assert sha(p/'application')==i['executable_SHA256']==m['original_binary_sha256']
    assert sha(p/'execution/application')==m['signed_binary_sha256']==lease['signed_binary_sha256']
    for name,digest in i['frozen'].items():assert sha(p/name)==digest,name
    assert m['launcher_SHA256']==i['frozen']['runtime/run_sdk_host.py'] and m['reservation_module_SHA256']==i['frozen']['runtime/lab_gpu_reservation.py']
    expected_mode='inventory' if mode=='inventory' else 'shared'
    assert m['arguments']==[expected_mode,str(i['registry_id'])] and r['mode']==expected_mode and r['requested_registry_ID']==i['registry_id']
    assert not r['matching_status'] and not r['truncated'] and r['user_client_type']==6 and not r['special_exclusive_type_used']
    assert not r['external_method_calls'] and not r['GPU_commands_submitted'] and not r['hardware_video_execution_proved'] and not r['system_modified']
    matching=[x for x in r['services'] if x['class']=='nvAccelerator' and x['vendor_ID']==0x10de and x['device_ID']==0x1198 and not x['class_status'] and not x['registry_status'] and not x['name_status']]
    assert len(matching)==1
    if mode=='inventory':
        assert r['status']=='INVENTORY_ONLY' and not r['open_attempts'] and not r['close_attempts'] and not r['candidate_count']
    elif mode=='wrong-target':
        assert i['registry_id']==1 and r['status']=='TARGET_NOT_QUALIFIED' and not r['candidate_count'] and not r['open_attempts'] and not r['close_attempts']
    else:
        assert i['registry_id']==matching[0]['registry_ID'] and r['candidate_count']==1 and matching[0]['candidate']
        if allow_refusal and r['status']=='OPEN_REFUSED':
            assert r['open_attempts']==1 and r['close_attempts']==0
            assert not r['connection_returned'] and r['open_status'] != 0
        else:
            assert r['status']=='OPEN_CLOSED' and r['open_attempts']==r['close_attempts']==1
            assert r['connection_returned'] and r['open_status']==r['close_status']==0
    observed = 'OBSERVED_REFUSAL' if mode=='shared' and r['status']=='OPEN_REFUSED' else 'PASS'
    return {'status':observed,'mode':mode,'gpu_registry_id':matching[0]['registry_ID'],
            'open_attempts':r['open_attempts'],'external_methods':0,'hardware_video_execution_proved':False,
            'driver_internal_effects_traced':False,'system_modified':False}

if __name__=='__main__':print(json.dumps(verify(sys.argv[1]),sort_keys=True))
