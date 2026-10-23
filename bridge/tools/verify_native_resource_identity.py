#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU oracle for native direct resource IDs, samples, queries and guards."""
from pathlib import Path
import base64
import struct
from public_large_scratch import read, sha
from verify_local_memory import verify_device_identity

MASK = (1<<32)-1
SENTINEL = 0xd15ea5ed
MODES = ['native','direct','wrong_texture','wrong_sampler','wrong_buffer','no_dispatch']


def icb_compile(result):
    verify_device_identity(result)
    assert result['library_loaded'] and result['function_created'] and not result['interposition']
    assert result['GPU_dispatches'] == result['GPU_command_buffers'] == 0
    assert result['function_encoder_created'] and result['encoded_length'] == 0
    assert not result['pipeline_created'] and result['outcome'] == 'PIPELINE_REFUSED'
    assert 'Unsupported indirect argument kind "air.command_buffer"' in result['pipeline_error']
    return dict(status='PASS_EXPECTED_COMPILER_REFUSAL',function_encoder_bytes=0,
        native_ICB_pipeline_created=False,first_compiler_refusal='air.command_buffer argument metadata',
        downstream_command_intrinsics_qualified=False,GPU_dispatches=0)


def reference(trial, count, mode):
    assert mode in MODES
    seed = 0x125ab700 + trial*97
    output = []
    for gid in range(count):
        x, y = (gid*3+trial)%12-4, (gid*5+trial*2)%12-4
        if mode == 'wrong_sampler': x,y = x%4,y%4
        else: x,y = max(0,min(3,x)),max(0,min(3,y))
        value = (((gid+8)*747796405+seed)&MASK)^0x12345678
        if mode == 'wrong_buffer': value ^= 0x2468ace1
        witnesses = [value^seed,gid*3,(value*5+trial)&MASK,0xc0010000^gid^0x00040104]
        for c,witness in enumerate(witnesses):
            texel = (x*47+y*29+c*37+(91 if mode == 'wrong_texture' else 13))%256
            output.append((texel^witness)&MASK if mode != 'no_dispatch' else SENTINEL)
    return output


def inspect(result):
    verify_device_identity(result)
    assert result['pointer_control_passed'] and result['GPU_dispatches'] == result['GPU_command_buffers'] == 0
    rows = {r['kind']:r for r in result['rows']}; assert len(rows) == 5
    for kind in ['pointer','texture','sampler']:
        r = rows[kind]; assert r['encoder_created'] and r['encoded'] and r['guards_intact']
        assert r['encoder_class'] == 'NVMTLIndirectArgumentEncoder' and r['encoded_length'] == r['alignment'] == 8
    assert rows['pointer']['pointer_matches_GPU_address_plus_offset']
    for kind in ['ICB','pipeline']: assert rows[kind]['encoder_created'] and rows[kind]['encoded_length'] == 0
    for kind in ['texture','sampler']:
        p = result[f'native_{kind}_ID']; assert p['returned'] and p['word'] > 0
        assert (rows[kind]['encoded_word'] & MASK) == p['word']
    factories = result['ICB_factories']; assert len(factories) == 2
    assert {r['render'] for r in factories} == {True,False}
    assert all(not r.get('created') and 'newIndirectCommandBufferWithDescriptor:maxCount:options:' in r['exception'] for r in factories)
    return dict(status='PASS_OBSERVED',native_texture_sampler_getters=True,
        pointer_encoder_bytes=8,texture_encoder_bytes=8,sampler_encoder_bytes=8,
        ICB_encoder_bytes=0,pipeline_encoder_bytes=0,ICB_creation_refusals=2,GPU_dispatches=0)


def execute(result, outputs):
    verify_device_identity(result); mode = result['mode']; assert mode in MODES + ['prepare']
    assert [r['offset'] for r in result['argument_layout']] == [0,8,16]
    if mode == 'prepare':
        assert result['status'] == 'PREPARED' and result['GPU_dispatches'] == result['GPU_command_buffers'] == 0
        return dict(status='PREPARED',GPU_dispatches=0)
    assert result['status'] == 'PASS' and result['native_shader'] and not result['interposition']
    assert result['user_dispatches'] == (0 if mode == 'no_dispatch' else 3)
    assert len(result['runs']) == 3
    checked = guards = differences = root_changes = 0; files = {}
    for trial,(r,count) in enumerate(zip(result['runs'],[16,65,257])):
        assert r['trial'] == trial and r['threads'] == count and r['seed'] == 0x125ab700+trial*97
        assert r['texture'] == (1 if mode == 'wrong_texture' else 0)
        assert r['sampler'] == (1 if mode == 'wrong_sampler' else 0)
        assert r['input'] == (1 if mode == 'wrong_buffer' else 0)
        assert r['mismatches'] == r['output_guard_mismatches'] == r['root_guard_mismatches'] == 0 and r['command_status'] == 4
        output,root = [Path(outputs)/f'trial-{trial}.{suffix}.bin' for suffix in ['output','root']]
        raw,argument = output.read_bytes(),root.read_bytes()
        assert len(raw) == (count+8)*16 and len(argument) == 152
        expected_guard = struct.pack('<I',SENTINEL)*16
        assert raw[:64] == raw[-64:] == expected_guard
        assert argument[:64] == argument[-64:] == bytes([0xa5])*64
        assert argument[64:88] == base64.b64decode(r['encoded_bytes_base64'],validate=True)
        native = base64.b64decode(r['native_bytes_base64'],validate=True); assert len(native) == 24
        if mode == 'native': assert argument[64:88] == native
        else:
            assert argument[64:88] == struct.pack('<3Q',r['texture_ID'],r['sampler_ID'],r['input_GPU_address_plus_offset'])
            assert int.from_bytes(native[:4],'little') == r['texture_ID']
            assert int.from_bytes(native[8:12],'little') == r['sampler_ID']
            assert native[16:] == argument[80:88]
        root_changes += sum(a!=b for a,b in zip(native,argument[64:88]))
        actual = list(struct.unpack('<'+'I'*(count*4),raw[64:-64]))
        expected = reference(trial,count,mode); assert actual == expected
        baseline = reference(trial,count,'native')
        different = sum(a!=b for a,b in zip(actual,baseline))
        if mode in ['native','direct']: assert different == 0
        else: assert different > 0
        differences += different; checked += len(actual); guards += 256
        for p in [output,root]:files[p.name] = sha(p)
    if mode != 'native': assert root_changes > 0
    return dict(status='PASS',mode=mode,GPU_dispatches=result['user_dispatches'],
        command_buffers=3,checked_uint32=checked,guard_bytes=guards,
        expected_differences_from_baseline=differences,changed_native_encoding_bytes=root_changes,
        files_SHA256=files,performance_benchmark=False)
