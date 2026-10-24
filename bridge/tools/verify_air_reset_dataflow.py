#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent arithmetic/branch/record oracle, CPU-only."""
from pathlib import Path
import hashlib
import struct
from public_large_scratch import read,sha
from verify_local_memory import verify_device_identity
from verify_air_render_reset import native_code

CASES=(('empty',0,16,7,0,32),('single',1,1,0,0,1),('prefix',7,16,3,0,8),
       ('full',16,16,9,0,32),('branch',16,16,1,1,32),('mask3',37,7,29,3,64),
       ('tail',37,16,17,0,32),('bad_magic',16,16,11,0,32),('null_context',16,16,11,0,32),
       ('large_capacity',16,17,11,0,32),('bad_size',16,16,11,0,32),('null_records',16,16,11,0,32),
       ('unaligned_records',16,16,11,0,32),('bad_version',16,16,11,0,32),('reserved',16,16,11,0,32),('zero_capacity',16,0,11,0,32))


def expected(case,execute):
    assert case in CASES
    name,count,capacity,seed,mask,width=case;result=[]
    for b,size in enumerate([1152,384,384]):
        data=bytearray(0xa5+b if i<64 or i>=size-64 else((i*37+17)&255 if b==0 else 0x6d)for i in range(size));result.append(data)
    indices=[int(format(i,'04b')[::-1],2)^(seed&15)if i<16 else i+16 for i in range(64)]
    for i,index in enumerate(indices):struct.pack_into('<I',result[2],64+4*i,index)
    reset_slots=[]
    if execute:
        for gid in range(count):
            index=indices[gid];x=((gid*1664525+seed)&0xffffffff)^index;selected=(x&mask)==0
            if selected:
                if name in ['single','prefix','full','branch','mask3','tail']and index<capacity:
                    result[0][64+64*index:128+64*index]=bytes(64);reset_slots.append(index)
                x^=0xa511e9b3
            else:x=(x+0x7f4a7c15)&0xffffffff
            shift=(gid&15)+1;value=(((x<<shift)|(x>>(32-shift)))^(index*0x9e3779b9))&0xffffffff
            struct.pack_into('<I',result[1],64+4*gid,value)
    assert len(reset_slots)==len(set(reset_slots)),'One writer per reset slot'
    return list(map(bytes,result)),reset_slots


def verify(path):
    path=Path(path);m=read(path/'inputs.json');d=read(path/'results.json');r=read(path/'execution/manifest.json')
    verify_device_identity(d);assert d==read(path/'execution/execution.stdout')
    assert r['exit_code']==0 and not r['SIGKILL_requested']and not r['authoritative_ps_status']
    lease=r['GPU_reservation'];assert lease['state']=='terminal'and lease['child_PID']==r['pid']and lease['exit_code']==0 and not lease['known_signed_processes_live']
    assert sha(path/'application')==m['executable_SHA256']==r['original_binary_sha256']
    assert sha(path/'execution/application')==r['signed_binary_sha256']==lease['signed_binary_sha256']
    for name,h in m['frozen'].items():assert sha(path/name)==h,name
    assert r['launcher_SHA256']==m['frozen']['runtime/run_sdk_host.py']and r['reservation_module_SHA256']==m['frozen']['runtime/lab_gpu_reservation.py']
    assert d['mode']==m['mode']and d['core_runtime_linked']is False
    assert sha(path/'assets'/(m['variant']+'.metallib'))==d['library_SHA256']
    code,metadata=native_code(path)
    assert r['arguments']==[str(path/'assets'/(m['variant']+'.metallib')),m['mode'],str(path/'outputs'),str(path/'certificate.json')]
    if m['mode']=='inspect':
        assert d['trials']==[]and d['compute_dispatches']==d['command_buffers']==0
        return dict(status='PASS',mode=m['mode'],variant=m['variant'],code_bytes=len(code),code_SHA256=d['code_SHA256'])
    cert=read(path/'certificate.json');assert sha(path/'certificate.json')==m['certificate_SHA256']
    assert cert['code_SHA256']==d['code_SHA256']and cert['library_SHA256']==d['library_SHA256']and cert['driver_SHA256']==m['driver_SHA256']and cert['no_native_call']is True
    assert cert['metadata_words']==metadata and cert['code_bytes']==len(code)
    assert len(d['trials'])==len(CASES)and d['command_buffers']==16
    execute=m['mode']=='execute';files={};reset=words=0
    for t,case in zip(d['trials'],CASES):
        assert tuple(t[k]for k in ['name','count','capacity','seed','mask','width'])==case
        assert t['dispatched']is execute and t['status']==4 and t['private_buffers']==4
        wanted,slots=expected(case,execute);reset+=len(slots);words+=case[1]if execute else 0
        assert set(t['files'])=={case[0]+'-'+str(i)+'.bin'for i in range(3)}
        for i,data in enumerate(wanted):
            name=case[0]+'-'+str(i)+'.bin';actual=(path/'outputs'/name).read_bytes()
            assert hashlib.sha256(actual).hexdigest()==t['files'][name]and actual==data,name
            files[name]=t['files'][name]
    assert d['compute_dispatches']==16*execute
    return dict(status='PASS',mode=m['mode'],variant=m['variant'],compute_dispatches=16*execute,
        checked_bytes=16*1920,guard_bytes=16*384,witness_words=words,reset_records=reset,files_SHA256=files)
