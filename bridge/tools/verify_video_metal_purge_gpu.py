#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independently validate raw Metal post-purge GPU results against a CPU oracle."""
import array, hashlib, json, sys
from pathlib import Path

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify(path):
    p=Path(path).resolve();i=read(p/'inputs.json');r=read(p/'results.json');m=read(p/'execution/manifest.json');lease=m['GPU_reservation'];mode=i['mode']
    assert mode in ('native','purge','negative') and r==read(p/'execution/execution.stdout')
    assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
    assert lease['state']=='terminal' and lease['exit_code']==0 and lease['child_PID']==m['pid'] and not lease['known_signed_processes_live']
    assert r['pid']==m['pid'] and r['uid']==r['euid']==i['user_UID']!=0 and r['mode']==mode
    assert r['gpu_registry_id']==i['registry_id'] and r['pci_registry_id']!=0
    assert m['arguments']==[mode,str(i['registry_id']),str(p/'assets/resource_sync.metallib'),str(p/'outputs')]
    assert sha(p/'application')==i['executable_SHA256']==m['original_binary_sha256']
    assert sha(p/'execution/application')==m['signed_binary_sha256']==lease['signed_binary_sha256']
    assert sha(p/'assets/resource_sync.metallib')==i['metallib_SHA256']
    for name,digest in i['frozen'].items():assert sha(p/name)==digest,name
    assert m['launcher_SHA256']==i['frozen']['runtime/run_sdk_host.py'] and m['reservation_module_SHA256']==i['frozen']['runtime/lab_gpu_reservation.py']
    n=r['elements'];seed=r['seed'];guard=r['guard_bytes_each'];assert n==1024*1024 and seed==0xfeed1234 and guard==64
    assert r['target_length']==n*4 and r['output_length']==n*4+2*guard and r['threadgroup_size']==32
    assert r['pipeline_read_max_threads']>=32 and r['pipeline_write_max_threads']>=32
    assert r['state_initial']==r['state_restored']==2
    if mode=='purge':assert [r['previous_empty'],r['state_empty'],r['previous_restore']]==[2,4,4]
    else:assert [r['previous_empty'],r['state_empty'],r['previous_restore']]==[0,0,0]
    raw_target=(p/'outputs/target.bin').read_bytes();raw_output=(p/'outputs/output.bin').read_bytes()
    assert len(raw_target)==n*4 and len(raw_output)==n*4+2*guard
    assert raw_output[:guard]==raw_output[-guard:]==b'\xa5'*guard
    assert sys.byteorder=='little';target=array.array('I');target.frombytes(raw_target);output=array.array('I');output.frombytes(raw_output[guard:-guard]);assert target.itemsize==4
    mask=0xffffffff;term=(seed*747796405)&mask;negative=mode=='negative'
    bad_target=bad_output=would_target=would_output=0
    for j,(actual_target,actual_output) in enumerate(zip(target,output)):
        initial=j^0x5a39d117;produced=((j*1664525)&mask)^seed;consumed=((initial+((j*1013904223)&mask))&mask)^term
        bad_target+=actual_target!=(initial if negative else produced);bad_output+=actual_output!=(0xa5a5a5a5 if negative else consumed)
        if negative:would_target+=actual_target!=produced;would_output+=actual_output!=consumed
    assert not bad_target and not bad_output
    if negative:
        assert not r['command_submitted'] and r['command_status']==0 and would_target>0 and would_output>0
        outcome='NEGATIVE_CONTROL_PASS'
    else:
        assert r['command_submitted'] and r['command_status']==4
        outcome='GPU_READ_WRITE_PASS'
    return {'verification':'PASS','outcome':outcome,'mode':mode,'gpu_registry_id':r['gpu_registry_id'],'pci_registry_id':r['pci_registry_id'],
            'elements':n,'cpu_words_compared':2*n,'guard_bytes_compared':2*guard,'target_mismatches':bad_target,'output_mismatches':bad_output,
            'negative_gpu_write_mismatches':would_target,'negative_gpu_read_mismatches':would_output,
            'target_SHA256':sha(p/'outputs/target.bin'),'output_SHA256':sha(p/'outputs/output.bin'),'GPU_execution_proved':not negative}

if __name__=='__main__':print(json.dumps(verify(sys.argv[1]),sort_keys=True))
