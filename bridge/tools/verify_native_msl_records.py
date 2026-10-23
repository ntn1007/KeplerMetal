#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent byte oracle for native C++ command-record lowering."""
from pathlib import Path
import struct
from public_large_scratch import read,sha
from verify_local_memory import verify_device_identity

MAGIC=0x4b504952
ERROR=0x80000000


def expected(operation,pipeline,storage,constant,dispatch=True):
    own,foreign=bytearray(b'\xa5'*1792),bytearray(b'\xa5'*1792)
    def row(which,index):return memoryview(which)[256+index*128:384+index*128]
    def reset(which,index):
        r=row(which,index);r[:]=bytes(128);struct.pack_into('<I',r,0,MAGIC)
    def word(index,offset,value):struct.pack_into('<I',row(own,index),offset,value)
    def long(index,offset,value):struct.pack_into('<Q',row(own,index),offset,value)
    def fail(index,code):
        r=row(own,index);flags=struct.unpack_from('<I',r,4)[0]
        word(index,4,flags|ERROR);word(index,76,code)
    if not dispatch or operation in [12,13,14,15,16,20]:return bytes(own),bytes(foreign)
    if operation in [0,1,2,3,4,6,7,8,9,17,18,19,21,22]:reset(own,0)
    if operation in [1,4,22]:
        word(0,4,383 if operation!=4 else 375);long(0,8,pipeline)
        for i,v in enumerate([2,3,4]):word(0,16+i*4,v)
        for i,v in enumerate([32,1,1]):word(0,32+i*4,v)
        for i,v in enumerate([storage,constant,storage+28]):long(0,48+i*8,v)
        long(0,104,constant+12);word(0,72,128)
    elif operation==2:
        word(0,4,2);word(0,28,1)
        for i,v in enumerate([64,4,2]):word(0,16+i*4,v)
        for i,v in enumerate([32,2,1]):word(0,32+i*4,v)
    elif operation==3:
        word(0,4,9);long(0,8,pipeline);row(own,1)[:]=bytes(row(own,0));reset(own,0)
    elif operation==5:fail(0,4)
    elif operation in [6,7,18,21]:fail(0,1)
    elif operation in [8,19]:fail(0,2)
    elif operation==9:fail(0,3)
    elif operation in [10,11]:
        reset(own,1);fail(1,5)
        if operation==11:reset(foreign,0)
    elif operation==17:
        word(0,4,128)
        for i,v in enumerate([1,2,3,4,5,6]):word(0,80+i*4,v)
    return bytes(own),bytes(foreign)


def verify(root):
    root=Path(root);d=read(root/'results.json');m=read(root/'execution/manifest.json');inputs=read(root/'inputs.json')
    assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and m['GPU_reservation']['state']=='terminal'
    assert sha(root/'application')==inputs['executable_SHA256']==m['original_binary_sha256']
    verify_device_identity(d);assert d['producer_backend']=='native_msl' and not d['record_execution'] and not d['instruction_import'] and not d['performance_benchmark']
    dispatch=d['mode']=='execute';assert dispatch or d['mode']=='no_dispatch'
    assert d['user_dispatches']==(23 if dispatch else 0) and d['command_buffers']==23 and len(d['cases'])==23
    files={};changed=0
    for operation,r in enumerate(d['cases']):
        assert r['operation']==operation and r['command_status']==4 and r['contexts_unchanged']
        assert r['pipeline_token']==(0x4b504950<<32)|1
        wanted=expected(operation,r['pipeline_token'],r['storage_address'],r['constant_address'],dispatch)
        for k,want in enumerate(wanted):
            path=root/'outputs'/f'case-{operation}-records-{k}.bin';actual=path.read_bytes()
            assert actual==want,(operation,k)
            changed+=sum(a!=0xa5 for a in actual);files[path.name]=sha(path)
    assert (changed>0)==dispatch
    return dict(status='PASS',mode=d['mode'],cases=23,user_dispatches=d['user_dispatches'],command_buffers=23,
        record_data_bytes=23*2*1024,guard_bytes=23*2*768,changed_bytes=changed,raw_SHA256=files,
        record_execution=False,performance_benchmark=False)
