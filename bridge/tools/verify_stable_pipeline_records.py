#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent byte oracle for stable-ID resolution, ordering and omission."""
from pathlib import Path
import hashlib,json,struct
from verify_local_memory import verify_device_identity
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
MAGIC=0x4b504952;TOKEN=0x4b504950;ERROR=0x80000000

def expected(operation,address,dispatch=True):
    data=bytearray(b'\xa5'*512)
    if not dispatch or operation in [10,11]:return bytes(data)
    words=[0]*32;words[0]=MAGIC
    if operation in [7,8,15,16]:words[1]=ERROR;words[19]=1
    elif operation==9:words[1]=ERROR|1;words[3]=TOKEN;words[19]=1
    else:
        candidate={0:0,1:2,2:3,3:2,4:2,5:2,6:1,12:2,13:0,14:3,17:2,18:0,19:0,20:3}[operation]
        local=16 if operation in [1,3,4,5,12,17]else 64 if operation==6 else 32
        groups=4 if operation==2 else 33 if operation==19 else 16 if operation==3 else 1
        words[1]=3 if operation==17 else 67
        words[2:4]=[candidate,TOKEN];words[4:7]=[groups,1,1];words[7]=int(operation in [3,19]);words[8:11]=[local,1,1]
        if operation!=17:
            offset=128 if operation in [1,3,4,5,12]else 64 if operation==6 else 4 if operation==18 else 0
            pointer=address+offset;words[16:18]=[pointer&0xffffffff,pointer>>32]
        if operation==14:words[1]|=4;words[18]=16
    record=struct.pack('<32I',*words)
    if operation==12:
        data[128:256]=struct.pack('<I',MAGIC)+bytes(124);data[256:384]=record
    else:data[128:256]=record
    return bytes(data)

def verify(root):
    root=Path(root);d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());inp=json.loads((root/'inputs.json').read_text())
    assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and m['GPU_reservation']['state']=='terminal'
    assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256']
    verify_device_identity(d)
    assert not d['record_execution'] and not d['instruction_import'] and not d['performance_benchmark'] and not d['system_modified']
    ids=d['current_pipeline_IDs']+[d['stale_pipeline_ID']];assert len(ids)==len(set(ids))==3 and all(x>>32==0x4b505350 and x&0xffffffff for x in ids)
    assert d['identity_API_refusals']==3 and d['scopes_restored']
    dispatch=d['mode']=='execute';assert dispatch or d['mode']=='no_dispatch'
    assert len(d['cases'])==21 and d['user_dispatches']==(21 if dispatch else 0) and d['command_buffers']==21
    raw={}
    for op,row in enumerate(d['cases']):
        assert row['operation']==op and row['command_status']==4 and row['context_and_guards_unchanged'] and 0<row['parameter_address']<1<<40
        path=root/'outputs'/row['file'];assert path.read_bytes()==expected(op,row['parameter_address'],dispatch),(op,row['file']);raw[row['file']]=sha(path)
        address=row['parameter_address'];assert 0<row['records_address']<1<<40
        context=struct.pack('<4IQ2I',0x4b504343 if op==11 else 0x4b505343,3,2,4,row['records_address'],128,0 if op==15 else 9 if op==16 else 4)
        for i,(identity,offset,local,groups)in enumerate(zip([ids[0],ids[1],ids[0],ids[0]],[0,64,128,0],[32,64,16,32],[2,8,16,2 if op==13 else 4])):
            context+=struct.pack('<QQ10I',identity,address+offset,groups,1,1,local,1,1,16 if (op==14 and i==3)or(op==20 and i==0)else 0,2,0,0)
        context+=bytes(4*56)
        path=root/'outputs'/row['context_file'];assert path.read_bytes()==b'\x5a'*128+context+b'\x5a'*128,(op,'context');raw[row['context_file']]=sha(path)
    return dict(status='PASS',cases=21,user_dispatches=d['user_dispatches'],record_bytes_checked=21*256,guard_bytes_checked=21*256,context_and_guard_bytes_checked=21*736,identity_API_refusals=3,stale_scope_pipeline_rejected_on_GPU=dispatch,raw_SHA256=raw,record_execution=False,performance_benchmark=False,full_objective_complete=False)
