#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent indexed record, inline binding table and raster reception."""
from pathlib import Path
import struct
from public_large_scratch import read,sha
from verify_indirect_render_ranges import verify_provenance
from verify_air_reset_render import verify_pipeline
from verify_render_state_catalogue import verify_rows

MODES=('indexed_gpu','indexed_native','indexed_reference','indexed_no_dispatch','indexed_no_dispatch_native',
 'indexed_foreign','indexed_foreign_native','indexed_wrong_kind','indexed_wrong_kind_native','indexed_last','indexed_last_native',
 'indexed_missing_table','indexed_missing_table_native','indexed_after_reset','indexed_after_reset_native','indexed_then_reset','indexed_then_reset_native','indexed_contracts')
SEEDS=(80,88,96,104,64,112,80,88)


def dispatches(mode):return not mode.startswith('indexed_no_dispatch')
def order(mode):return 3 if mode.startswith('indexed_last')else 2 if mode.startswith('indexed_after_reset')else 1 if mode.startswith('indexed_then_reset')else 0
def suppressed(mode):return mode.startswith(('indexed_foreign','indexed_wrong_kind','indexed_missing_table'))


def draw_parameters(trial,slot,last=False):
    gid=0 if slot==1 else 1;x=((gid*1664525+SEEDS[trial])&0xffffffff)^slot
    first=3*((x>>3)&1);count=3*((x>>4)&3);instances=(x>>6)&1
    return(3-first,3,1)if last else(first,count,instances)


def transform(mode,trial,slot,raw,ids):
    if slot not in(1,3)or not dispatches(mode):return raw
    if suppressed(mode)or order(mode)==1:return bytes(64)
    identity=0 if order(mode)==2 else struct.unpack_from('<Q',raw,32)[0]
    if identity and identity not in ids:
        if order(mode)!=3:return bytes(64)
        identity=0 # First rejected command reset the slot; the last draw follows.
    first,count,instances=draw_parameters(trial,slot,order(mode)==3)
    kind=1 if slot==1 else 2
    return struct.pack('<8IQ6I',0x4b505353,kind,count,instances,first,2 if kind==1 else 0xfffffffe,kind,0,identity,*([0]*6))


def why(mode,trial,slot,state,previous,records,ids,adapted):
    if slot not in(1,3)or not dispatches(mode):return previous
    r=records[slot];kind=1 if slot==1 else 2
    if r[0]!=0x4b505353:return 1
    if r[8]not in ids:return 5
    if r[8]!=ids[state]:return 6
    if r[1]!=kind:return 2
    count,instances,first=r[2:5]
    if not(first<=6 and count<=6-first and instances<=1 and r[5]==(2 if kind==1 else 0xfffffffe)and r[6]==kind):return 3
    return 0


def extra_buffers(row,mode):
    t=row['trial'];r=row['AIR_reset'];missing=mode.startswith('indexed_missing_table');wrong=mode.startswith('indexed_wrong_kind')
    indices=(3,1,11,7)if wrong else(1,3,11,7)
    assert(r['capacity'],r['count'],r['seed'],r['mask'],r['target_slot'],r['order'])==(4,4,SEEDS[t],0,indices[0],order(mode))
    assert r['dispatched']is dispatches(mode)and r['public_getter']=='function'and(r['encoded_length'],r['alignment'])==(8,8)
    assert not r['reflection_requested']and r['reflection_type']==0 and r['client_GPU_address_construction']is False
    assert r['root_refusals']==(['index_records_overlap','index_root_alias']if mode=='indexed_contracts'and t==0 else[])
    for f in ['root_context_alive_before_commit','argument_encoder_released_before_commit','root_function_restored_before_commit']:assert row[f]is True
    for f in ['context_storage_mode','records_storage_mode','root_storage_mode','indices_storage_mode','output_storage_mode']:assert r[f]==(0 if f=='root_storage_mode'else 2)
    assert r['index_storage_modes']==([0,2]if mode=='indexed_contracts'else[2,2])
    assert(r['index_binding_count'],r['index_binding_table_offset'])==((0,0)if missing else(4,128))
    context,records,rootAddress=(r[k]for k in ['context_GPU_address','records_GPU_address','root_GPU_address'])
    buffers=r['index_buffer_GPU_addresses'];inputs=r['index_input_GPU_addresses']
    assert len(buffers)==len(inputs)==2
    addresses=[context,records,rootAddress,*buffers]
    assert len(set(addresses))==len(addresses)and all(type(a)is int and 0<a<2**40 and a%16==0 for a in addresses)
    if mode.startswith('indexed_foreign'):
        assert len(set(inputs))==2 and not set(inputs)&set(addresses)and all(type(a)is int and 0<a<2**40 and a%16==0 for a in inputs)
    else:assert inputs==(list(reversed(buffers))if wrong else buffers)
    ctx=bytearray(b'\xa5'*(160 if missing else 384));struct.pack_into('<4I2Q',ctx,64,0x4b505243,1,4,64,records,0)
    if not missing:
        struct.pack_into('<4I2Q',ctx,96,0x4b504958,1,4,48,context+64,0)
        for j,(slot,kind)in enumerate([(1,1),(3,2)]):
            for state,identity in enumerate(row['identifiers']):struct.pack_into('<3Q4IQ',ctx,128+(j*2+state)*48,identity,buffers[j],6*(2 if kind==1 else 4),slot,kind,6,0,0)
    root=bytearray(b'\xa5'*136);struct.pack_into('<Q',root,64,context)
    indexData=bytearray(b'\xa5'*144);struct.pack_into('<4I',indexData,64,*indices)
    output=bytearray(b'\xa5'*144)
    if dispatches(mode):
        for gid,index in enumerate(indices):
            x=((gid*1664525+SEEDS[t])^index)^0xa511e9b3;shift=gid+1;value=(((x<<shift)|(x>>(32-shift)))^(index*0x9e3779b9))&0xffffffff;struct.pack_into('<I',output,64+gid*4,value)
    result={'reset-context':ctx,'reset-root':root,'reset-indices':indexData,'reset-output':output}
    if mode.startswith('indexed_foreign'):result.update({'foreign-index-0':bytes(256),'foreign-index-1':bytes(256)})
    return result


def verify(out):
    out=Path(out);m,_=verify_provenance(out);d=read(out/'results.json');mode=d['mode'];assert mode in MODES
    assert m['typed_indexed_render']and m['render_argument_encoders']and m['air_reset']and not m['typed_render_draw']
    variant='reference'if mode=='indexed_reference'else'lowered';cert=read(out/'assets'/('reset-'+variant+'.certificate.json'))
    program=verify_pipeline(out,dict(d,mode='air_reference'if variant=='reference'else'air_gpu'),m)
    extras={};programs=[];rows={r['trial']:r for r in d['runs']}
    for t,row in rows.items():
        extras[t]=extra_buffers(row,mode);p=row['AIR_reset']['ordinary_pipeline'];name=f'reset-native-frame-{t}.bin'
        assert p['file']==name and p['own_CPU_staging_code']and not p['code_replaced']and not p['constructor_observer_installed']
        assert sha(out/'outputs'/name)==p['code_SHA256']==cert['code_SHA256']and(out/'outputs'/name).stat().st_size==p['code_bytes']==cert['code_bytes'];programs.append(name)
    proof=verify_rows(dict(d,mode='native'if mode.endswith('native')else'gpu'),out,extra_buffers=extras,
        record_transform=lambda t,s,b:transform(mode,t,s,b,rows[t]['identifiers']),reason_transform=lambda t,s,state,old,records,ids,a:why(mode,t,s,state,old,records,ids,a))
    assert {p.name for p in(out/'outputs').iterdir()if p.is_file()}==set(proof['files_SHA256'])|set(programs)
    events=d['scope_events'];missing=mode.startswith('indexed_missing_table')
    for op in ['register_render_record_function','create_render_record_argument_context']:assert sum(e['operation']==op for e in events)==8
    for e in events:
        if e['operation']=='register_render_record_function':assert e['native_pipeline_factories_preserved']and e['native_reflection_preserved']and not e['Apple_native_ICB_identity']and e['schema']['kind']=='render_records_v1'
        if e['operation']=='create_render_record_argument_context':assert e['index_bindings']==(0 if missing else 4)and e['index_buffers_retained']is(not missing)and e['index_table_inline']is(not missing)
    prepare=[e for e in events if e['operation']=='prepare_render_record_arguments'];assert len(prepare)==(8 if dispatches(mode)else 0)
    for e in prepare:assert e['root_bytes']==8 and e['indirect_resources_declared']and e['roots_retained_until_completion']and e['native_pipeline_unchanged']
    proof.update(mode=mode,indexed_program=program,indexed_dispatches=8 if dispatches(mode)else 0,
        arithmetic_witness_words=32 if dispatches(mode)else 0,root_guard_bytes=4096,ordinary_native_programs_checked=8,
        owned_binding_rows_checked=0 if missing else 32,client_GPU_address_construction=False,API_refusals=2 if mode=='indexed_contracts'else 0)
    return proof
