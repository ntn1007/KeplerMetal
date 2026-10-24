#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate a construction-only observation, without claiming GPU support."""
from pathlib import Path
import hashlib
import struct
from public_large_scratch import read,sha
from verify_local_memory import verify_device_identity


def parse_native_payload(blob):
    assert 32<=len(blob)<=8*1024*1024
    version,total=struct.unpack_from('<2I',blob)
    assert version in [7,8,9]and total==len(blob)
    offset=8;parts=[]
    for _ in range(32):
        assert offset+16<=len(blob)
        next_,kind,size=struct.unpack_from('<QII',blob,offset)
        assert size<=len(blob)-offset-16
        parts.append((kind,blob[offset+16:offset+16+size]))
        if not next_:assert offset+16+size==len(blob);break
        assert next_>=16+size and next_<=len(blob)-offset-16
        offset+=next_
    else:raise AssertionError('Too many sections')
    assert parts[0]==(1,struct.pack('<I',5))
    metadata=[data for kind,data in parts if kind==0x10004]
    code=[data for kind,data in parts if kind==0x10005]
    assert len(metadata)==len(code)==1 and len(metadata[0])==232
    assert code[0]and len(code[0])%64==0
    return code[0],list(struct.unpack('<58I',metadata[0]))


def classify(result):
    if result['outcome']=='PIPELINE_CREATED_NOT_EXECUTED':return 'pipeline_created_not_executed'
    error=result.get('pipeline_error','')
    if 'Unsupported indirect argument kind "air.command_buffer"'in error:return 'command_argument_metadata_refused'
    return 'unclassified_pipeline_refusal'


def verify(path):
    path=Path(path);m=read(path/'inputs.json');r=read(path/'execution/manifest.json');d=read(path/'results.json')
    verify_device_identity(d)
    assert r['exit_code']==0 and r['SIGKILL_requested']is False and r['authoritative_ps_status']==''
    lease=r['GPU_reservation'];assert lease['state']=='terminal'and lease['child_PID']==r['pid']and lease['exit_code']==0 and not lease['known_signed_processes_live']
    capture=m.get('capture_native_code',False)
    assert r['arguments']==[str(path/'assets'/(m['case']+'.metallib')),m['case']]+([str(path/'captures')]if capture else[])
    assert sha(path/'application')==m['executable_SHA256']==r['original_binary_sha256']
    assert sha(path/'execution/application')==r['signed_binary_sha256']==lease['signed_binary_sha256']
    for name,digest in m['frozen'].items():assert sha(path/name)==digest,name
    assert r['launcher_SHA256']==m['frozen']['runtime/run_sdk_host.py']and r['reservation_module_SHA256']==m['frozen']['runtime/lab_gpu_reservation.py']
    assert d==read(path/'execution/execution.stdout')and d['case']==m['case']
    assert d['library_loaded']is True and d['function_created']is True
    for field in ['GPU_command_buffers','GPU_dispatches','GPU_resources_allocated']:assert type(d[field])is int and d[field]==0
    assert d['runtime_linked']is False and d['interposition']is capture
    assert d['outcome']in ['PIPELINE_CREATED_NOT_EXECUTED','PIPELINE_REFUSED']
    if d['pipeline_created']:
        assert d['outcome']=='PIPELINE_CREATED_NOT_EXECUTED'and d['pipeline_error']==''
        assert d['thread_width']>0 and d['max_threads']>0
    else:
        assert d['outcome']=='PIPELINE_REFUSED'and d['pipeline_error']and d['error_domain']
    if m['case']=='pointer_control':assert d['pipeline_created']is True
    captured=[]
    if capture:
        c=d['capture'];assert c['observer_still_installed_before_restore']is True and c['constructor_restored']is True
        assert c['input_arguments_replaced']is False and c['capture_stage']=='native_constructor_input_not_resident_code'
        for item in c['records']:
            assert item['saved']is True and item['constructor_returned_nonnull']is True and item['inputs_replaced']is False
            file=path/'captures'/item['file'];assert file.parent==path/'captures'and file.name==item['file']
            blob=file.read_bytes();assert len(blob)==item['bytes']and sha(file)==item['SHA256']
            code,metadata=parse_native_payload(blob)
            program=dict(code_bytes=len(code),code_SHA256=hashlib.sha256(code).hexdigest(),metadata_words=metadata)
            if m.get('post_constructor_code',False):
                assert item['post_constructor_code_saved']is True
                name=item['post_constructor_code_file'];assert Path(name).name==name
                after=(path/'captures'/name).read_bytes()
                assert after==code and len(after)==item['post_constructor_code_bytes']
                assert hashlib.sha256(after).hexdigest()==item['post_constructor_code_SHA256']
                assert item['post_constructor_read_scope']=='own CPU staging copy; not resident GPU readback'
                program['post_constructor_CPU_copy_identical']=True
            captured.append(program)
        assert len(captured)==(1 if d['pipeline_created']else 0)
    return dict(status='OBSERVED',case=m['case'],classification=classify(d),
        pipeline_created=d['pipeline_created'],pipeline_error=d['pipeline_error'],
        GPU_dispatches=0,GPU_execution_proved=False,library_SHA256=m['frozen']['assets/'+m['case']+'.metallib'],native_constructor_programs=captured)
