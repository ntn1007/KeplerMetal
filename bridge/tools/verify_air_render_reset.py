#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Portable byte oracle; no Metal calls and no trust in host pass counters."""
from pathlib import Path
import hashlib
import struct
from public_large_scratch import read,sha
from verify_local_memory import verify_device_identity


def parse_reset_native(blob):
    """Version-8 constructor sections with checked zero alignment padding."""
    assert 32<=len(blob)<=8*1024*1024 and len(blob)%8==0
    assert struct.unpack_from('<2I',blob)==(8,len(blob))
    offset=8;parts=[]
    for _ in range(16):
        assert offset%8==0 and offset+16<=len(blob)
        next_,kind,size=struct.unpack_from('<QII',blob,offset)
        end=offset+16+size;aligned=(end+7)&~7
        assert end<=len(blob)and aligned<=len(blob)and not any(blob[end:aligned])
        parts.append((kind,blob[offset+16:end]))
        if not next_:
            assert aligned==len(blob)
            break
        assert next_==aligned-offset and aligned+16<=len(blob)
        offset=aligned
    else:raise AssertionError('Too many sections')
    assert [k for k,_ in parts]==[1,0x10004,0x10000,0x10001,0x10002,0x10003,0x10005,0x10006]
    data=dict(parts);assert data[1]==struct.pack('<I',5)and len(data[0x10004])==232
    code=data[0x10005];assert code and len(code)%64==0
    return code,list(struct.unpack('<58I',data[0x10004]))

CASES=(('prefix',16,3,1),('full',16,1,32),('small',7,1,8),('single',1,1,1),
       ('over_index',4,7,1),('empty',16,0,1),('bad_magic',16,1,32),('bad_version',16,1,32),
       ('zero_capacity',0,1,32),('large_capacity',17,1,32),('bad_size',16,1,32),
       ('reserved',16,1,32),('null_records',16,1,32),('unaligned_records',16,1,32),('null_context',16,1,32))


def expected(name,capacity,groups,width,execute):
    assert (name,capacity,groups,width)in CASES
    data=bytearray(0xa5 if i<64 or i>=1088 else(i*37+17)&255 for i in range(1152))
    if execute and name in ['prefix','full','small','single','over_index']:
        for slot in range(min(capacity,groups*width)):
            data[64+64*slot:128+64*slot]=bytes(64)
    return bytes(data)


def native_code(path):
    path=Path(path);d=read(path/'results.json');capture=d['capture']
    assert capture['constructor_restored']and capture['observer_still_installed_before_restore']and not capture['input_arguments_replaced']
    assert len(capture['records'])==1
    item=capture['records'][0]
    assert item['saved']and item['post_constructor_code_saved']and item['constructor_returned_nonnull']and not item['inputs_replaced']
    for field in ['file','post_constructor_code_file']:assert Path(item[field]).name==item[field]
    blob=(path/'outputs/captures'/item['file']).read_bytes()
    assert len(blob)==item['bytes']and hashlib.sha256(blob).hexdigest()==item['SHA256']
    code,metadata=parse_reset_native(blob)
    after=(path/'outputs/captures'/item['post_constructor_code_file']).read_bytes()
    assert code==after and len(code)==item['post_constructor_code_bytes']
    assert hashlib.sha256(code).hexdigest()==item['post_constructor_code_SHA256']==d['code_SHA256']
    return code,metadata


def verify(path):
    path=Path(path);m=read(path/'inputs.json');d=read(path/'results.json');r=read(path/'execution/manifest.json')
    assert d==read(path/'execution/execution.stdout');verify_device_identity(d)
    assert r['exit_code']==0 and not r['SIGKILL_requested']and r['authoritative_ps_status']==''
    lease=r['GPU_reservation'];assert lease['state']=='terminal'and lease['exit_code']==0 and lease['child_PID']==r['pid']and not lease['known_signed_processes_live']
    assert sha(path/'application')==m['executable_SHA256']==r['original_binary_sha256']
    assert sha(path/'execution/application')==r['signed_binary_sha256']==lease['signed_binary_sha256']
    for name,digest in m['frozen'].items():assert sha(path/name)==digest,name
    assert r['launcher_SHA256']==m['frozen']['runtime/run_sdk_host.py']and r['reservation_module_SHA256']==m['frozen']['runtime/lab_gpu_reservation.py']
    assert d['mode']==m['mode']and d['core_runtime_linked']is False
    assert d['library_SHA256']==sha(path/'assets'/(m['variant']+'.metallib'))
    code,metadata=native_code(path)
    assert r['arguments']==[str(path/'assets'/(m['variant']+'.metallib')),m['mode'],str(path/'outputs'),str(path/'certificate.json')]
    if m['mode']=='inspect':
        assert d['compute_dispatches']==d['command_buffers']==0 and d['trials']==[]
        return dict(status='PASS',mode=m['mode'],variant=m['variant'],code_bytes=len(code),code_SHA256=d['code_SHA256'])
    cert=read(path/'certificate.json');assert sha(path/'certificate.json')==m['certificate_SHA256']
    assert cert['driver_SHA256']==m['driver_SHA256']and cert['code_SHA256']==d['code_SHA256']and cert['library_SHA256']==d['library_SHA256']and cert['no_native_call']is True
    assert cert['code_bytes']==len(code)and cert['metadata_words']==metadata
    assert len(d['trials'])==len(CASES)and d['command_buffers']==15
    dispatches=0;changed=0;files={}
    for item,case in zip(d['trials'],CASES):
        name,capacity,groups,width=case
        assert [item[k]for k in ['name','capacity','groups','width']]==list(case)
        execute=bool(groups and m['mode']=='execute');assert item['dispatched']is execute
        assert item['status']==4 and item['records_storage_mode']==item['context_storage_mode']==2
        assert item['file']==name+'.bin';blob=(path/'outputs'/item['file']).read_bytes()
        assert hashlib.sha256(blob).hexdigest()==item['SHA256']
        wanted=expected(*case,execute)
        assert blob==wanted,name
        baseline=expected(*case,False);changed+=sum(a!=b for a,b in zip(blob,baseline));dispatches+=execute
        files[item['file']]=item['SHA256']
    assert d['compute_dispatches']==dispatches
    return dict(status='PASS',mode=m['mode'],variant=m['variant'],trials=15,compute_dispatches=dispatches,
        checked_bytes=15*1152,guard_bytes=15*128,changed_bytes=changed,files_SHA256=files)
