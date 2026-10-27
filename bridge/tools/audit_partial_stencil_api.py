#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit immutable signed stencil runs and same-runtime barrier regressions."""
import datetime
import hashlib
import json
import math
import struct
import subprocess
import sys
from pathlib import Path
from verify_partial_stencil_api import verify, read, sha
from verify_partial_general_api import verify as verify_previous
from verify_uniform_icb_3d import verify as verify_uniform


def audit(paths):
    if len(paths) != 18:
        raise ValueError('Need pipeline capture, prepare, eight cases, four repeats, two previous-shader and two uniform regressions')
    capture, *all_paths = [Path(p).resolve() for p in paths]
    paths, uniform_paths = all_paths[:15], all_paths[15:]
    capture_inputs = read(capture / 'inputs.json')
    capture_result = read(capture / 'results.json')
    capture_execution = read(capture / 'execution/manifest.json')
    for name, digest in capture_inputs['frozen'].items():
        if sha(capture / name) != digest:
            raise ValueError('Pipeline capture frozen input differs')
    if (capture_result != read(capture / 'execution/execution.stdout') or capture_result['GPU_dispatch'] or capture_result['committed'] or
        capture_execution['exit_code'] or capture_execution['GPU_reservation']['state'] != 'terminal' or
        capture_result['library_SHA256'] != sha(capture / 'assets/shader.metallib') or
        capture_result['records'][0]['function'] != 'partial_buffer_stencil' or
        capture_result['records'][0]['static_threadgroup_bytes'] != 0):
        raise ValueError('Construction-only pipeline capture differs')
    commands = (capture / 'capture/partial_buffer_stencil.commands.bin').read_bytes()
    if (len(commands) != 464 or hashlib.sha256(commands).hexdigest() != capture_result['records'][0]['command_SHA256'] or
        struct.unpack_from('<I', commands, 184 + 0x44)[0] & 0x3ffff != 0 or
        struct.unpack_from('<I', commands, 184 + 0xb8)[0] >> 24 != 11 or
        struct.unpack_from('<I', commands, 184 + 0x50)[0] & 255 != 6):
        raise ValueError('Captured native command profile differs')
    subprocess.run(['codesign', '--verify', '--strict', str(capture / 'execution/application')], check=True, capture_output=True, timeout=15)
    rows = []
    for index, path in enumerate(paths):
        previous = index >= 13
        verify_fn = verify_previous if previous else verify
        result = verify_fn(path)
        case = 0 if index == 0 else index - 1 if index <= 8 else (0, 0, 6, 6, 0, 6)[index - 9]
        mode = 'prepare' if index == 0 else 'execute'
        if result != read(path / 'verification.stdout') or read(path / 'verification-execution.json') != {'exit_code': 0, 'isolated_interpreter': True} or result['case'] != case or result['mode'] != mode:
            raise ValueError('Result or case differs')
        subprocess.run(['codesign', '--verify', '--strict', str(path / 'execution/application')], check=True, capture_output=True, timeout=15)
        for trial in read(path / 'results.json')['runs'][1:]:
            proof = trial['proof']; owners = proof['owner_original_profiles']; addresses = proof['descriptor_GPU_addresses']
            stream = bytearray()
            if len(owners) != result['regions'] or len({x['registration_id'] for x in owners}) != 1:
                raise ValueError('Owner registration differs')
            for owner, address in zip(owners, addresses):
                if owner['descriptor_GPU_address'] != address or address % 256 or address >> 8 > 0xffffffff or owner['constant_buffer_valid_mask'] != 6 or math.prod(owner['groups_shape']) * math.prod(owner['local_shape']) > 128:
                    raise ValueError('Resident record differs')
                stream += struct.pack('<6I', 0x200120ad, address >> 8, 0x200120af, 3, 0x20012044, 0)
            if hashlib.sha256(stream).hexdigest() != proof['stream_SHA256']:
                raise ValueError('Resident launch stream differs')
        rows.append((path, result, read(path / 'inputs.json'), read(path / 'execution/manifest.json')))
    for row, base in zip(rows[9:13], (rows[1], rows[1], rows[7], rows[7])):
        if row[1]['rows'] != base[1]['rows']:
            raise ValueError('Fresh-process repeat outputs differ')
    uniform = []
    for path, form in zip(uniform_paths, ('groups', 'threads')):
        result = verify_uniform(path)
        if result != read(path / 'verification.stdout') or read(path / 'verification-execution.json')['exit_code'] != 0 or result['mode'] != 'execute' or result['form'] != form:
            raise ValueError('Uniform regression differs')
        subprocess.run(['codesign', '--verify', '--strict', str(path / 'execution/application')], check=True, capture_output=True, timeout=15)
        uniform.append((path, result, read(path / 'inputs.json'), read(path / 'execution/manifest.json')))
    comparable = lambda row: {k: h for k, h in row[1]['raw_SHA256'].items() if not k.endswith('.commands.bin')}
    if len(comparable(uniform[0])) != 180 or comparable(uniform[0]) != comparable(uniform[1]):
        raise ValueError('Uniform group/thread outputs differ')
    cohort = rows + uniform
    if len({r[3]['pid'] for r in cohort}) != len(cohort) or len({r[2]['runtime_archive_SHA256'] for r in cohort}) != 1 or len({r[2]['registry_id'] for r in cohort}) != 1 or any(r[2]['profile'] != rows[0][2]['profile'] for r in cohort):
        raise ValueError('PID, runtime, GPU or profile differs')
    ordered = sorted(cohort, key=lambda r: r[3]['started_at'])
    for a, b in zip(ordered, ordered[1:]):
        if datetime.datetime.fromisoformat(a[3]['completed_at']) >= datetime.datetime.fromisoformat(b[3]['started_at']):
            raise ValueError('Signed GPU hosts overlap')
    if len({r[2]['build_inputs_SHA256'] for r in rows[:13]}) != 1:
        raise ValueError('Stencil build identity differs')
    if capture_result['library_SHA256'] != rows[0][2]['library_SHA256'] or capture_inputs['profile'] != rows[0][2]['profile'] or capture_result['registry_id'] != rows[0][2]['registry_id']:
        raise ValueError('Pipeline capture is not the tested device, profile and library')
    stencil = rows[:13]
    return {'audit': 'PASS', 'stencil_prepare_hosts': 1, 'stencil_execution_hosts': 12,
            'grid_cases': [{'grid': r[1]['grid'], 'local': r[1]['local'], 'regions': r[1]['regions'], 'threads': r[1]['threads']} for r in rows[1:9]],
            'repeated_cases': [0, 0, 6, 6],
            'stencil_user_command_buffers': sum(r[1]['user_command_buffers'] for r in stencil),
            'stencil_invocations': sum(r[1]['threads'] for r in stencil),
            'stencil_output_uint32_values': sum(r[1]['uint32_output_values_checked'] for r in stencil),
            'negative_refusal_observations': sum(r[1]['negative_cases'] for r in stencil),
            'previous_shader_regression_hosts': 2,
            'previous_shader_invocations': sum(r[1]['threads'] for r in rows[13:]),
            'uniform_regression_hosts': 2,
            'uniform_invocations': sum(r[1]['GPU_invocations_counted'] for r in uniform),
            'uniform_uint32_values': sum(r[1]['correct_uint32_words'] for r in uniform),
            'uniform_paired_data_files': len(comparable(uniform[0])),
            'runtime_archive_SHA256': rows[0][2]['runtime_archive_SHA256'],
            'core_source_SHA256': rows[0][2]['frozen']['src/KeplerCPUICB.mm'],
            'shader_source_SHA256': capture_inputs['frozen']['src/partial_buffer_stencil.metal'],
            'shader_library_SHA256': rows[0][2]['library_SHA256'],
            'manifest_SHA256': rows[0][2]['manifest_SHA256'],
            'host_source_SHA256': rows[0][2]['frozen']['src/partial_stencil_api_probe.mm'],
            'execution_manifest_SHA256': [sha(r[0] / 'execution/manifest.json') for r in cohort],
            'scope': 'Exact experimental shader and manifest; immutable input and disjoint output; serial process-local project ICB',
            'native_apple_ICB': False, 'transparent_integration': False, 'system_modified': False}


if __name__ == '__main__':
    print(json.dumps(audit(sys.argv[1:]), indent=2, sort_keys=True))
