#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent CPU samples, full guards and native packet/metadata checks."""
from pathlib import Path
import base64
import struct
from public_large_scratch import read, sha
from verify_local_memory import verify_device_identity

SENTINEL = 0xd15ea5ed
MASK = 0xffffffff
MODES = [p+s for p in ['native','cpu'] for s in ['', '_wrong_texture', '_wrong_sampler', '_wrong_buffer', '_no_dispatch']]


def reference(trial, count, mode):
    assert mode in MODES
    seed = 0x125ab700+trial*97
    result = []
    for gid in range(count):
        x, y = (gid*3+trial)%12-4, (gid*5+trial*2)%12-4
        if mode.endswith('_wrong_sampler'): x,y = x%4,y%4
        else: x,y = max(0,min(3,x)),max(0,min(3,y))
        value = (((gid+8)*747796405+seed)&MASK)^0x12345678
        if mode.endswith('_wrong_buffer'): value ^= 0x2468ace1
        witnesses = [value^seed,gid*3,(value*5+trial)&MASK,0xc0010000^gid^0x00040104]
        for c,w in enumerate(witnesses):
            t = (x*47+y*29+c*37+(91 if mode.endswith('_wrong_texture') else 13))%256
            result.append(SENTINEL if mode.endswith('_no_dispatch') else t^w)
    return result


def verify_metadata(d, outputs, profile):
    assert d['status'] == 'PREPARED_NOT_SUBMITTED' and d['GPU_submissions'] == 0
    assert d['GPU_execution_proved'] is False and d['command_status'] == 0 and d['system_modified'] is False
    assert d['root_bytes'] == 24 and d['root_alignment'] == 8
    assert d['native_registers'] == 17 and d['native_spill_bytes'] == 0 and d['native_code_bytes'] == 1216
    assert d['constant_buffer_valid_mask'] == 7 and d['native_literal_bank_0_bytes'] == 256 and d['literal_code_end_relation']
    expected = profile['functions'][0]
    assert len(d['reflection']) == len(expected['buffers']) == 3
    for actual,pinned in zip(d['reflection'], expected['buffers']):
        assert actual['type'] == 0
        for key in ['name','index','data_type','alignment','data_size','access','active']: assert actual[key] == pinned[key],key
    assert [(m['type'],m['offset'],m['index']) for m in d['reflection'][0]['members']] == [(58,0,0),(59,8,1),(60,16,2)]
    raw,qmd,variant = [(outputs/p).read_bytes() for p in ['native.commands.bin','native.qmd.bin','native.variant.bin']]
    assert len(raw) == d['command_bytes'] == 464 and len(qmd) == 256 and len(variant) == 128
    at = 0; packets = []; found = []
    while at<len(raw):
        h, = struct.unpack_from('<I',raw,at); mode,count,method = h>>29,(h>>16)&0x1fff,(h&0x1fff)*4
        assert mode in [1,3,4]
        length = 0 if mode == 4 else 4*count
        assert at+4+length<=len(raw)
        packets.append(dict(offset=at,method=method,mode=mode,count=count))
        if (method,mode,count) == (0x1b4,3,64): found.append(raw[at+4:at+4+length])
        at += 4+length
    assert packets == d['packets'] and found == [qmd]
    word = lambda p,o:struct.unpack_from('<I',p,o)[0]
    assert word(qmd,0xb8)>>24 == word(variant,48) == 17
    assert word(qmd,0x50)&255 == 7 and word(qmd,0x78)>>15 == 256
    code,code_bytes = struct.unpack_from('<2Q',variant,16)
    cb0 = word(qmd,0x74)|((word(qmd,0x78)&255)<<32)
    assert cb0 == code+((code_bytes+255)&~255)
    return dict(status='PASS_PREPARED_NOT_SUBMITTED',GPU_dispatches=0,checked_uint32=0,guard_bytes=0,command_bytes=464,native_registers=17,packet_count=len(packets))


def verify_execution(d, outputs):
    mode = d['mode']; assert mode in MODES
    cpu = mode.startswith('cpu'); dispatch = not mode.endswith('_no_dispatch')
    assert d['status'] == 'PASS' and d['native_shader'] is True
    assert d['CPU_ICB'] is cpu and d['interposition'] is cpu and d['performance_benchmark'] is False
    assert [r['offset'] for r in d['argument_layout']] == [0,8,16]
    assert d['user_dispatches'] == (3 if dispatch else 0) and len(d['runs']) == 3
    assert bool(d['scope_events']) is cpu
    if cpu:
        events = d['scope_events']
        rows = lambda name:[e for e in events if e['operation'] == name]
        assert len(rows('scope_install')) == len(rows('registered_manifest_library')) == len(rows('scope_restore')) == 1
        assert rows('scope_restore')[0]['device_class_restored'] is True
        assert rows('scope_restore')[0]['system_modified'] is False
        materialized = rows('materialize_CPU_command')
        assert len(materialized) == len(rows('initialize_resident_QMD')) == len(rows('prepare_resident_compute_commands')) == 3
        for e in rows('prepare_resident_compute_commands'):
            assert e['location'] == 0 and e['length'] == 1 and e['user_kernel_dispatches'] == 0 and e['GPU_initializers'] == 1
        for e in materialized:
            r = e['relocation']
            assert e['command_bytes'] == 464 and e['user_kernel_invocations'] == 0
            assert r['function'] == 'sample_icb_arguments' and r['library_SHA256'] == d['library_SHA256']
            assert r['binding_layout_v2'] is True and r['native_register_count'] == 17
            assert r['constant_buffer_valid_mask'] == 7 and r['parameters_offset'] == 0 and r['constant_buffer_bytes'] == 512
            assert [(b['index'],b['offset']) for b in r['bindings']] == [(0,64),(1,64),(2,0)]
            literal = r['native_literal_bank_0']
            assert literal['bytes'] == 256 and literal['native_code_bytes'] == 1216 and literal['variant_owner_retained'] is True
        executed = rows('executeCommandsInBuffer'); assert len(executed) == (3 if dispatch else 0)
        for e in executed:
            assert e['executed_indices'] == [0] and e['concurrent_record_execution'] is False
            p = e['evidence']
            assert p['raw_packet_copies'] == p['sequence_elements'] == p['sequence_repetitions'] == 1
            assert p['command_bytes'] == 464 and p['native_preparation_GPU_dispatches'] == 0
            assert p['launches_suppressed'] is False and p['system_modified'] is False
    checked = guards = differences = 0; files = {}
    for trial,(r,n) in enumerate(zip(d['runs'],[16,65,257])):
        seed = 0x125ab700+trial*97
        assert (r['trial'],r['threads'],r['seed']) == (trial,n,seed)
        for field,suffix in [('texture','texture'),('sampler','sampler'),('input','buffer')]: assert r[field] == int(mode.endswith('_wrong_'+suffix))
        assert r['mismatches'] == r['output_guard_mismatches'] == r['root_guard_mismatches'] == 0 and r['command_status'] == 4
        names = [f'trial-{trial}.{suffix}.bin' for suffix in ['output','root','private-root','parameters','input-0','input-1']]
        raw,root,private,params,*inputs = [(outputs/p).read_bytes() for p in names]
        assert len(raw) == (((n+31)//32)*32+8)*16
        assert len(root) == len(private) == 152 and root == private
        assert root[:64] == root[88:] == b'\xa5'*64
        native = base64.b64decode(r['native_bytes_base64'],validate=True)
        encoded = base64.b64decode(r['encoded_bytes_base64'],validate=True)
        assert len(native) == 24 and native == encoded == root[64:88]
        assert struct.unpack_from('<I',native,0)[0] == r['texture_ID'] > 0
        assert struct.unpack_from('<I',native,8)[0] == r['sampler_ID'] > 0
        assert struct.unpack_from('<Q',native,16)[0] == r['input_GPU_address_plus_offset'] > 32
        assert raw[:64] == struct.pack('<I',SENTINEL)*16
        assert raw[64+n*16:] == struct.pack('<I',SENTINEL)*((len(raw)-64-n*16)//4)
        actual = list(struct.unpack('<'+'I'*n*4,raw[64:64+n*16]))
        assert actual == reference(trial,n,mode)
        different = sum(a!=b for a,b in zip(actual,reference(trial,n,'native')))
        assert (different>0) == ('_' in mode)
        differences += different
        assert len(params) == 512 and params[16:] == b'\xa5'*496
        assert params[:16] == struct.pack('<4I',n,seed,trial,0)
        for bank,input_bytes in enumerate(inputs):
            values = [(((i*747796405+seed)&MASK)^0x12345678^(0x2468ace1 if bank else 0)) for i in range(n+32)]
            assert input_bytes == struct.pack('<'+'I'*len(values),*values)
        checked += len(actual); guards += len(raw)-n*16+256+496
        files.update({name:sha(outputs/name) for name in names})
    return dict(status='PASS',mode=mode,GPU_dispatches=d['user_dispatches'],checked_uint32=checked,guard_bytes=guards,
        differences_from_baseline=differences,files_SHA256=files,caller_retains_and_declares_indirect_resources=True,
        new_runtime_resource_lifetime_support=False,performance_benchmark=False)


def verify(out):
    out = Path(out); d,m,receipt = [read(out/p) for p in ['results.json','inputs.json','execution/manifest.json']]
    assert receipt['exit_code'] == 0 and receipt['SIGKILL_requested'] is False and not receipt['authoritative_ps_status']
    assert receipt['original_binary_sha256'] == m['executable_SHA256']
    assert sha(out/'execution/application') == receipt['signed_binary_sha256']
    assert receipt['GPU_reservation']['state'] == 'terminal' and not receipt['GPU_reservation']['known_signed_processes_live']
    for key,folder in [('source_SHA256',''), ('runtime_SHA256','runtime'), ('oracle_SHA256','oracles'), ('assets_SHA256','')]:
        for name,digest in m[key].items(): assert sha(out/folder/name) == digest,name
    verify_device_identity(d)
    profile = read(out/'consumer-profile.json')
    assert sha(out/'consumer.metallib') == d['library_SHA256'] == profile['library_SHA256']
    result = verify_metadata(d,out/'outputs',profile) if m['mode'] == 'metadata' else verify_execution(d,out/'outputs')
    return dict(result,device_identity=d['device_identity'],library_SHA256=d['library_SHA256'])
