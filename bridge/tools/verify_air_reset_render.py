#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU raster/record/reset oracle, native certificate and ownership evidence."""
from pathlib import Path
import hashlib
import struct
from public_large_scratch import read,sha
from verify_indirect_render_ranges import verify_provenance
from verify_render_state_catalogue import verify_rows
from verify_air_render_reset import parse_reset_native

MODES=('air_gpu','air_native','air_reference','air_no_reset','air_no_reset_native','air_bad_context','air_bad_context_native')


def reset_witness(gid,index):
    x=(((gid*1664525+3)&0xffffffff)^index)^0xa511e9b3
    shift=(gid&15)+1
    return (((x<<shift)|(x>>(32-shift)))^(index*0x9e3779b9))&0xffffffff


def extra_buffers(row,mode,root_storage_mode=2):
    r=row['AIR_reset'];dispatch=not mode.startswith('air_no_reset')
    assert r['dispatched']is dispatch and[r[k]for k in ['capacity','count','seed','mask','target_slot']]==[4,4,3,0,3]
    for field in ['context_storage_mode','records_storage_mode','root_storage_mode','indices_storage_mode','output_storage_mode']:assert r[field]==(root_storage_mode if field=='root_storage_mode'else 2)
    addresses=[r[k]for k in ['context_GPU_address','records_GPU_address','root_GPU_address']]
    assert len(set(addresses))==3 and all(type(a)is int and 0<a<2**40 and a%16==0 for a in addresses)
    ctx=bytearray(b'\xa5'*160);struct.pack_into('<4I2Q',ctx,64,0x4b505243^int(mode.startswith('air_bad_context')),1,4,64,r['records_GPU_address'],0)
    root=bytearray(b'\xa5'*136);struct.pack_into('<Q',root,64,r['context_GPU_address'])
    indices=bytearray(b'\xa5'*144);struct.pack_into('<4I',indices,64,3,11,7,15)
    output=bytearray(b'\xa5'*144)
    if dispatch:
        struct.pack_into('<4I',output,64,*(reset_witness(i,index)for i,index in enumerate([3,11,7,15])))
    return {'reset-context':ctx,'reset-root':root,'reset-indices':indices,'reset-output':output}


def verify_pipeline(out,d,m):
    variant='reference'if d['mode']=='air_reference'else'lowered';receipt=d['reset_pipeline'];capture=receipt['capture']
    assert receipt['ownership']=='NS_RETURNS_RETAINED MRC factory / ARC caller'and receipt['observer_restored_before_scope']is True
    assert capture['constructor_restored']and capture['observer_still_installed_before_restore']and not capture['input_arguments_replaced']
    assert len(capture['records'])==1;item=capture['records'][0]
    assert item['saved']and item['post_constructor_code_saved']and item['constructor_returned_nonnull']and not item['inputs_replaced']
    for name in ['file','post_constructor_code_file']:assert Path(item[name]).name==item[name]
    blob=(out/'outputs/reset-captures'/item['file']).read_bytes();code,metadata=parse_reset_native(blob)
    assert len(blob)==item['bytes']and hashlib.sha256(blob).hexdigest()==item['SHA256']
    assert code==(out/'outputs/reset-captures'/item['post_constructor_code_file']).read_bytes()
    assert hashlib.sha256(code).hexdigest()==item['post_constructor_code_SHA256']==receipt['code_SHA256']
    cert=read(out/'assets'/('reset-'+variant+'.certificate.json'))
    assert cert['metadata_words']==metadata and cert['code_bytes']==len(code)and cert['no_native_call']is True
    assert cert['code_SHA256']==receipt['code_SHA256']and cert['library_SHA256']==receipt['library_SHA256']and cert['driver_SHA256']==receipt['driver_SHA256']==m['driver_SHA256']
    assert sha(out/'assets'/('reset-'+variant+'.metallib'))==cert['library_SHA256']
    return dict(variant=variant,code_SHA256=receipt['code_SHA256'],code_bytes=len(code))


def verify(out):
    out=Path(out);m,_=verify_provenance(out);d=read(out/'results.json');mode=d['mode'];assert mode in MODES and m['air_reset']is True
    program=verify_pipeline(out,d,m)
    adapted=dict(d,mode='native'if mode.endswith('native')else'gpu')
    target=3 if mode in ['air_gpu','air_native','air_reference']else None
    extras={row['trial']:extra_buffers(row,mode)for row in d['runs']}
    proof=verify_rows(adapted,out,reset_slot=target,extra_buffers=extras)
    proof.update(mode=mode,reset_program=program,reset_dispatches=0 if mode.startswith('air_no_reset')else 8,
        reset_witness_words=0 if mode.startswith('air_no_reset')else 32,reset_guard_bytes=8*4*128,
        reset_root_CPU_read_for_candidate=False)
    return proof
