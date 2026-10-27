#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent exact byte oracle for a bounded compute-only GPU cohort."""
from pathlib import Path
import struct
from public_large_scratch import read, sha
from verify_local_memory import verify_device_identity
from verify_air_render_reset import native_code

MODES = ('active', 'wrong_token', 'foreign_source', 'wrong_slot', 'row_reserved',
         'bad_extension', 'bad_header', 'no_dispatch')


def expected(mode):
    assert mode in MODES
    record = bytearray(b'\xa5'*64 + b'\x5a'*64 + b'\xa5'*64)
    struct.pack_into('<Q', record, 96, 0x101)
    witness = bytearray(b'\xa5'*64 + b'\x6d'*4 + b'\xa5'*64)
    if mode != 'no_dispatch':
        struct.pack_into('<I', witness, 64, 0x4b505350)
    if mode not in ('no_dispatch', 'bad_header'):
        identity = 0x202 if mode == 'active' else 0
        words = [0x4b505353, 0, 3, 1, 0, 0, 0, 0, identity, 0, 0, 0, 0, 0, 0, 0]
        struct.pack_into('<16I', record, 64, *words)
    return bytes(record), bytes(witness)


def verify(path):
    path = Path(path); m = read(path/'inputs.json'); d = read(path/'results.json'); r = read(path/'execution/manifest.json')
    verify_device_identity(d); assert d == read(path/'execution/execution.stdout')
    assert r['exit_code'] == 0 and not r['SIGKILL_requested'] and not r['authoritative_ps_status']
    lease = r['GPU_reservation']; assert lease['state'] == 'terminal' and lease['child_PID'] == r['pid'] and lease['exit_code'] == 0 and not lease['known_signed_processes_live']
    assert sha(path/'application') == m['executable_SHA256'] == r['original_binary_sha256']
    assert sha(path/'execution/application') == r['signed_binary_sha256'] == lease['signed_binary_sha256']
    for name, digest in m['frozen'].items(): assert sha(path/name) == digest, name
    assert r['launcher_SHA256'] == m['frozen']['runtime/run_sdk_host.py'] and r['reservation_module_SHA256'] == m['frozen']['runtime/lab_gpu_reservation.py']
    assert m['profile'] == 'typed-pipeline-binding-air28-experiment-v1' and m['variant'] == 'lowered'
    assert d['mode'] == m['mode'] and m['mode'] in MODES and d['core_runtime_linked'] is False
    assert d['command_buffers'] == 1 and d['command_status'] == 4 and d['compute_dispatches'] == (m['mode'] != 'no_dispatch')
    assert d['library_SHA256'] == sha(path/'assets/lowered.metallib')
    code, metadata = native_code(path); cert = read(path/'certificate.json')
    assert sha(path/'certificate.json') == m['certificate_SHA256'] and cert['driver_SHA256'] == m['driver_SHA256']
    assert cert['code_SHA256'] == d['code_SHA256'] and cert['library_SHA256'] == d['library_SHA256'] and cert['no_native_call'] is True
    assert cert['code_bytes'] == len(code) and cert['metadata_words'] == metadata
    assert r['arguments'] == [str(path/'assets/lowered.metallib'), m['mode'], str(path/'outputs'), str(path/'certificate.json')]
    for name, wanted in zip(('records', 'witness'), expected(m['mode'])):
        file = path/'outputs'/(name+'.bin')
        assert sha(file) == d[name+'_SHA256'] and file.read_bytes() == wanted, name
    return {'status':'PASS_COMPUTE_ONLY', 'mode':m['mode'], 'dispatches':d['compute_dispatches'],
            'checked_bytes':324, 'gpu_rendering_proved':False, 'code_SHA256':d['code_SHA256']}
