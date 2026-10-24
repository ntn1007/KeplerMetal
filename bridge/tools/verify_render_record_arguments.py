#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recompute public root encoding, owned resources and raster effects."""
from pathlib import Path
import hashlib
import struct
from public_large_scratch import read,sha
from verify_indirect_render_ranges import verify_provenance
from verify_render_state_catalogue import verify_rows
from verify_air_reset_render import extra_buffers,verify_pipeline

MODES=('arguments_gpu','arguments_native','arguments_device','arguments_reflection','arguments_arrays','arguments_reuse','arguments_no_reset','arguments_no_reset_native','arguments_contracts')
REFUSALS=('bad_library_pin','bad_function_root_index','duplicate_context','wrong_execution_ICB',
          'record_offset_alignment','short_record_buffer','wrong_queue','unretained_CB',
          'wrong_setter_index','unprepared_ICB','private_root','misaligned_root','short_root',
          'unsupported_buffer_setter','off_thread_ICB','wrong_device_descriptor_index','wrong_device_descriptor_array',
          'unexported_root','tampered_root','second_preparation','setter_after_preparation','setter_after_restore')


def argument_buffers(row,mode):
    assert mode in MODES
    r=row['AIR_reset'];trial=row['trial'];dispatch=not mode.startswith('arguments_no_reset')
    expected_getter={'arguments_device':'device','arguments_reflection':'function_reflection'}.get(mode,'function')
    assert r['public_getter']==expected_getter and(r['encoded_length'],r['alignment'])==(8,8)
    assert r['reflection_requested']is(mode=='arguments_reflection')and r['reflection_type']==(85 if mode=='arguments_reflection'else 0)
    assert r['client_GPU_address_construction']is False
    assert r['root_refusals']==(list(REFUSALS)if mode=='arguments_contracts'and trial==0 else[])
    for field in ['root_context_alive_before_commit','argument_encoder_released_before_commit','root_function_restored_before_commit']:assert row[field]is True
    extra=extra_buffers(row,'air_gpu'if dispatch else'air_no_reset',root_storage_mode=0)
    if mode=='arguments_reuse':extra['reset-spare-root']=bytearray(extra['reset-root'])
    return extra


def verify(out):
    out=Path(out);m,_=verify_provenance(out);d=read(out/'results.json');mode=d['mode']
    assert mode in MODES and m['render_argument_encoders']is True and m['air_reset']is True
    program=verify_pipeline(out,d,m);dispatch=not mode.startswith('arguments_no_reset')
    extras={};native_program_files=[];getters=[]
    cert=read(out/'assets/reset-lowered.certificate.json')
    for row in d['runs']:
        trial=row['trial'];r=row['AIR_reset'];extras[trial]=argument_buffers(row,mode);getters.append(r['public_getter'])
        p=r['ordinary_pipeline'];name=f'reset-native-frame-{trial}.bin';assert p['file']==name
        assert p['own_CPU_staging_code']is True and p['code_replaced']is False and p['constructor_observer_installed']is False
        blob=(out/'outputs'/name).read_bytes();assert len(blob)==p['code_bytes']==cert['code_bytes']
        assert hashlib.sha256(blob).hexdigest()==p['code_SHA256']==cert['code_SHA256'];native_program_files.append(name)
    adapted=dict(d,mode='native'if mode.endswith('native')else'gpu')
    proof=verify_rows(adapted,out,reset_slot=3 if dispatch else None,extra_buffers=extras)
    files={p.name for p in(out/'outputs').iterdir()if p.is_file()}
    assert files==set(proof['files_SHA256'])|set(native_program_files)
    events=d['scope_events'];registrations=[e for e in events if e['operation']=='register_render_record_function']
    assert len(registrations)==8
    for e in registrations:
        assert e['schema']['kind']=='render_records_v1'and e['schema']['encoded_length']==8 and e['schema']['native_encoded_length']==0
        assert e['native_pipeline_factories_preserved']and e['native_reflection_preserved']and not e['Apple_native_ICB_identity']
    assert len([e for e in events if e['operation']=='create_render_record_argument_context'])==8
    assert len([e for e in events if e['operation']=='prepare_render_record_arguments'])==(8 if dispatch else 0)
    for e in events:
        if e['operation']=='prepare_render_record_arguments':assert e['root_bytes']==8 and e['root_offset']==64 and e['indirect_resources_declared']and e['roots_retained_until_completion']and e['native_pipeline_unchanged']
    proof.update(mode=mode,reset_program=program,reset_dispatches=8 if dispatch else 0,reset_witness_words=32 if dispatch else 0,
        reset_guard_bytes=8*4*128+(8*128 if mode=='arguments_reuse'else 0),ordinary_native_programs_checked=8,
        client_GPU_address_construction=False,root_getters=getters,API_refusals=len(REFUSALS)if mode=='arguments_contracts'else 0)
    return proof
