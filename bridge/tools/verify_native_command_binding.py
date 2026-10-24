#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Observe owned code bytes and uncommitted QMDs; never run a GPU program."""
from pathlib import Path
import hashlib
import struct
from public_large_scratch import read,sha
from verify_local_memory import verify_device_identity
from verify_native_command_boundary import parse_native_payload


def decode_qmd(data):
    assert data and len(data)%4==0
    offset=0;qmd=[];count_packets=0
    while offset<len(data):
        assert offset+4<=len(data)
        header=struct.unpack_from('<I',data,offset)[0];offset+=4
        mode=header>>29;count=(header>>16)&0x1fff;channel=(header>>13)&7;method=(header&0x1fff)*4
        assert channel==1 and mode in [1,3,4]and count>0
        size=0 if mode==4 else count*4;assert size<=len(data)-offset
        if method==0x1b4 and mode==3 and count==64:qmd.append(data[offset:offset+size])
        offset+=size;count_packets+=1
    assert len(qmd)==1
    q=qmd[0];word=lambda at:struct.unpack_from('<I',q,at)[0]
    result=dict(version=word(0x48)&15,major_version=(word(0x48)>>4)&15,
        groups=[word(0x30),word(0x34)&65535,word(0x34)>>16],
        local=[word(0x48)>>16,word(0x4c)&65535,word(0x4c)>>16],
        program_offset=word(0x20),registers=word(0xb8)>>24,packet_count=count_packets,
        QMD_SHA256=hashlib.sha256(q).hexdigest())
    assert result['version']==6 and result['major_version']==0
    assert result['groups']==result['local']==[1,1,1]
    return result


def verify(path):
    path=Path(path);m=read(path/'inputs.json');r=read(path/'execution/manifest.json');d=read(path/'results.json');files={}
    verify_device_identity(d);assert d['status']=='OBSERVED'and d['case']==m['case']and d['mode']==m['mode']
    assert r['exit_code']==0 and r['SIGKILL_requested']is False and r['authoritative_ps_status']==''
    lease=r['GPU_reservation'];assert lease['state']=='terminal'and lease['child_PID']==r['pid']and lease['exit_code']==0 and not lease['known_signed_processes_live']
    assert r['arguments']==[str(path/'assets'/(m['case']+'.metallib')),m['case'],str(path/'outputs'),m['mode']]
    assert sha(path/'application')==m['executable_SHA256']==r['original_binary_sha256']
    assert sha(path/'execution/application')==r['signed_binary_sha256']==lease['signed_binary_sha256']
    for name,digest in m['frozen'].items():assert sha(path/name)==digest,name
    assert r['launcher_SHA256']==m['frozen']['runtime/run_sdk_host.py']and r['reservation_module_SHA256']==m['frozen']['runtime/lab_gpu_reservation.py']
    assert d==read(path/'execution/execution.stdout')
    assert d['suspect_compute_CB_committed']is False and d['submitted_compute_dispatches']==0
    assert d['core_runtime_linked']is False and d['native_code_modified_by_probe']is False and d['performance_benchmark']is False
    def contents(name):
        assert Path(name).name==name
        p=path/'outputs'/name;files[name]=sha(p);return p.read_bytes()
    capture=d['capture'];assert capture['constructor_restored']is True and capture['observer_still_installed_before_restore']is True
    assert capture['input_arguments_replaced']is False and len(capture['records'])==1
    item=capture['records'][0];blob=contents(item['file']);assert len(blob)==item['bytes']and files[item['file']]==item['SHA256']
    assert item['saved']is True and item['constructor_returned_nonnull']is True and item['inputs_replaced']is False
    original,_=parse_native_payload(blob);post=contents(item['post_constructor_code_file'])
    assert item['post_constructor_code_saved']is True and post==original and len(post)==item['post_constructor_code_bytes']
    assert files[item['post_constructor_code_file']]==item['post_constructor_code_SHA256']
    stages=['constructed']if m['mode']=='inspect'else['constructed','pipeline-bound','buffers-bound','dispatch-encoded','encoding-ended']
    snapshots=d['CPU_snapshots'];assert [s['stage']for s in snapshots]==stages
    codes=[]
    for snapshot in snapshots:
        code=contents(snapshot['file']);codes.append(code)
        assert snapshot['code_bytes']==len(code)and files[snapshot['file']]==snapshot['SHA256']
        assert snapshot['code_buffer_offset']<=snapshot['code_buffer_length']
        assert len(code)<=snapshot['code_buffer_length']-snapshot['code_buffer_offset']
        assert snapshot['code_GPU_address']==snapshot['code_buffer_GPU_address']+snapshot['code_buffer_offset']
    assert codes[0]==original
    qmd=None
    if m['mode']=='inspect':assert d['encoded_compute_dispatches']==0
    else:
        assert d['encoded_compute_dispatches']==1 and d['suspect_compute_CB_status']==0
        assert contents('input.bin')==bytes(1024)and contents('output.bin')==b'\xa5'*1024
        raw=contents('uncommitted.commands.bin');assert len(raw)==d['uncommitted_commands_bytes']and files['uncommitted.commands.bin']==d['uncommitted_commands_SHA256']
        qmd=decode_qmd(raw);assert qmd['program_offset']==snapshots[3]['code_GPU_address']&0xffffffff
        assert qmd['registers']==snapshots[3]['registers']
    readbacks=d['readbacks'];expected=['before-binding','after-encoding']if m['mode'].startswith('readback')else[]
    assert [row['stage']for row in readbacks]==expected and d['committed_blit_CBs']==len(readbacks)
    matches=[]
    for i,row in enumerate(readbacks):
        data=contents(row['file']);size=row['code_bytes']
        assert row['command_status']==4 and row['committed_encoder']=='blit'and row['compute_encoder_created']is False
        assert len(data)==size+128 and data[:64]==data[-64:]==b'\xa5'*64 and files[row['file']]==row['SHA256']
        assert row['copy_encoded']is(m['mode']=='readback')
        if m['mode']=='readback_no_copy':assert data==b'\xa5'*len(data)
        matches.append(data[64:-64]==codes[0 if i==0 else -1])
    if m['mode']=='readback_no_copy':assert matches==[False,False]
    return dict(status='OBSERVED',case=m['case'],mode=m['mode'],CPU_code_stages=len(codes),
        CPU_code_changed_after_construction=any(code!=original for code in codes),
        code_buffer_storage_modes=[s['code_buffer_storage_mode']for s in snapshots],
        resident_readbacks_match_CPU=matches,committed_blit_CBs=len(readbacks),
        submitted_compute_dispatches=0,encoded_uncommitted_dispatches=d['encoded_compute_dispatches'],
        constructor_code_SHA256=hashlib.sha256(original).hexdigest(),QMD=qmd,files_SHA256=files,
        native_ICB_execution_qualified=False,performance_benchmark=False)
