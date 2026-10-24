#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Typed triangle draws, operation order, owned roots and CPU raster reception."""
from pathlib import Path
import struct
from public_large_scratch import read,sha
from verify_indirect_render_ranges import verify_provenance
from verify_air_reset_render import verify_pipeline
from verify_render_state_catalogue import verify_rows

MODES=('draw_gpu','draw_native','draw_reference','draw_no_dispatch','draw_no_dispatch_native','draw_after_reset','draw_after_reset_native','draw_then_reset','draw_then_reset_native')
SEEDS=(80,88,96,80,104,112,16,80)


def dispatches(mode):return not mode.startswith('draw_no_dispatch')
def order(mode):return 1 if mode.startswith('draw_then_reset')else 2 if mode.startswith('draw_after_reset')else 0


def transform(mode,trial,slot,raw):
    if slot or not dispatches(mode):return raw
    if order(mode)==1:return bytes(64)
    seed=SEEDS[trial];identity=0 if order(mode)==2 else struct.unpack_from('<Q',raw,32)[0]
    return struct.pack('<8IQ6I',0x4b505353,0,3*((seed>>4)&3),(seed>>6)&1,5+3*((seed>>3)&1),0,(seed>>8)&3,0,identity,*([0]*6))


def why(mode,trial,slot,state,old,records,ids,adapted):
    if slot or not dispatches(mode):return old
    r=records[0]
    if r[0]!=0x4b505353:return 1
    if r[8]not in ids:return 5
    if r[8]!=ids[state]:return 6
    n,instances,first=r[2:5]
    if not(5<=first<=11 and n<=11-first and instances<=1 and r[5]==r[6]==0):return 3
    return 0


def extra_buffers(row,mode):
    trial=row['trial'];r=row['AIR_reset'];active=dispatches(mode)
    assert(r['capacity'],r['count'],r['seed'],r['mask'],r['target_slot'],r['order'])==(4,4,SEEDS[trial],0,0,order(mode))
    assert r['dispatched']is active and r['public_getter']=='function'and(r['encoded_length'],r['alignment'])==(8,8)
    assert not r['root_refusals']and not r['reflection_requested']and r['reflection_type']==0 and r['client_GPU_address_construction']is False
    for f in ['root_context_alive_before_commit','argument_encoder_released_before_commit','root_function_restored_before_commit']:assert row[f]is True
    for f in ['context_storage_mode','records_storage_mode','root_storage_mode','indices_storage_mode','output_storage_mode']:assert r[f]==(0 if f=='root_storage_mode'else 2)
    addresses=[r[k]for k in ['context_GPU_address','records_GPU_address','root_GPU_address']]
    assert len(set(addresses))==3 and all(type(a)is int and 0<a<2**40 and a%16==0 for a in addresses)
    ctx=bytearray(b'\xa5'*160);struct.pack_into('<4I2Q',ctx,64,0x4b505243,1,4,64,r['records_GPU_address'],0)
    root=bytearray(b'\xa5'*136);struct.pack_into('<Q',root,64,r['context_GPU_address'])
    indices=bytearray(b'\xa5'*144);values=(0,11,7,15);struct.pack_into('<4I',indices,64,*values)
    output=bytearray(b'\xa5'*144)
    if active:
        for gid,index in enumerate(values):
            x=((gid*1664525+SEEDS[trial])^index)^0xa511e9b3;shift=gid+1
            value=(((x<<shift)|(x>>(32-shift)))^(index*0x9e3779b9))&0xffffffff;struct.pack_into('<I',output,64+gid*4,value)
    return {'reset-context':ctx,'reset-root':root,'reset-indices':indices,'reset-output':output}


def verify(out):
    out=Path(out);m,_=verify_provenance(out);d=read(out/'results.json');mode=d['mode'];assert mode in MODES
    assert m['typed_render_draw']and m['render_argument_encoders']and m['air_reset']
    variant='reference'if mode=='draw_reference'else'lowered'
    program=verify_pipeline(out,dict(d,mode='air_reference'if variant=='reference'else'air_gpu'),m)
    cert=read(out/'assets'/('reset-'+variant+'.certificate.json'));extras={};program_files=[]
    for row in d['runs']:
        trial=row['trial'];extras[trial]=extra_buffers(row,mode);p=row['AIR_reset']['ordinary_pipeline'];name=f'reset-native-frame-{trial}.bin'
        assert p['file']==name and p['own_CPU_staging_code']and not p['code_replaced']and not p['constructor_observer_installed']
        assert sha(out/'outputs'/name)==p['code_SHA256']==cert['code_SHA256']and(out/'outputs'/name).stat().st_size==p['code_bytes']==cert['code_bytes'];program_files.append(name)
    adapted=dict(d,mode='native'if mode.endswith('native')else'gpu')
    proof=verify_rows(adapted,out,extra_buffers=extras,record_transform=lambda t,s,r:transform(mode,t,s,r),
        reason_transform=lambda t,s,b,old,records,ids,a:why(mode,t,s,b,old,records,ids,a))
    assert {p.name for p in(out/'outputs').iterdir()if p.is_file()}==set(proof['files_SHA256'])|set(program_files)
    events=d['scope_events']
    for op in ['register_render_record_function','create_render_record_argument_context']:
        assert sum(e['operation']==op for e in events)==8
    for e in events:
        if e['operation']=='register_render_record_function':
            assert e['schema']['kind']=='render_records_v1'and e['schema']['encoded_length']==8 and e['schema']['native_encoded_length']==0
            assert e['native_pipeline_factories_preserved']and e['native_reflection_preserved']and not e['Apple_native_ICB_identity']
    prepare=[e for e in events if e['operation']=='prepare_render_record_arguments'];assert len(prepare)==(8 if dispatches(mode)else 0)
    for e in prepare:assert e['indirect_resources_declared']and e['roots_retained_until_completion']and e['native_pipeline_unchanged']and e['root_bytes']==8
    proof.update(mode=mode,producer_program=program,typed_draw_dispatches=8 if dispatches(mode)else 0,
        arithmetic_witness_words=32 if dispatches(mode)else 0,root_guard_bytes=4096,ordinary_native_programs_checked=8,
        client_GPU_address_construction=False,operation_order=order(mode))
    return proof
