#!/usr/bin/env python3
"""Independent raw oracle and lifetime contract checks; never launches GPU work."""
import argparse
import hashlib
import json
import struct
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, reason):
    if not value:
        raise ValueError(reason)


def verify(root, current, portable=False):
    inputs = json.loads((root / 'inputs.json').read_text())
    data = json.loads((root / 'results.json').read_text())
    process = json.loads((root / 'execution/manifest.json').read_text())
    require(process['exit_code'] == 0 and not process['SIGKILL_requested'] and
            not process['authoritative_ps_status'], 'child not successfully terminal')
    for name, digest in inputs['source_hashes'].items():
        require(sha(root / name) == digest, 'frozen source differs: ' + name)
        if current:
            folder = 'src' if name.startswith('Kepler') else 'tools'
            require(sha(Path(__file__).resolve().parents[1] / folder / name) == digest,
                    'current source differs: ' + name)
    require(sha(root / 'indirect_compute_probe.metallib') == inputs['library_SHA256'] ==
            'b15f9b198ba326811f0a61f64fc32ac7cc185d04db63fa8e04f86075e8450a8d',
            'unqualified native library')
    if not portable:
        require(sha(root / 'cpu_icb_lifetime_probe') == process['original_binary_sha256'] and
                sha(root / 'execution/cpu_icb_lifetime_probe') == process['signed_binary_sha256'],
                'executed binary differs')
    commands = json.loads((root / 'commands.json').read_text())
    require(len(commands) == 2 and all(c['exit_code'] == 0 for c in commands),
            'build/observe failed')
    mode = data['mode']
    require(mode in ('prepare', 'execute') and data['device_class_restored'] and
            not data['system_modified'] and data['integration_level'] == 1, 'scope differs')
    cases = ['default_retained_drop_ICB', 'unretained_drop_ICB_not_submitted',
             'automatic_scope_restore_before_commit']
    require(len(data['cases']) == 3, 'missing lifecycle case')
    hashes = {}
    for index, row in enumerate(data['cases']):
        require(row['case'] == cases[index] and row['seed'] == 0x7654 + 97 * index,
                'case/seed differs')
        for field in ['ICB_released_before_commit', 'scope_released_before_commit',
                      'device_class_restored_before_commit', 'ended_encoder_already_released']:
            require(row[field], field + ' failed')
        require(row['automatic_scope_release'] == (index == 2), 'automatic restoration differs')
        retained = index != 1
        require(row['command_buffer_retainedReferences'] == retained and
                row['private_output_alive_before_commit'] == retained and
                row['private_counter_alive_before_commit'] == retained,
                'private resource ownership did not follow retainedReferences')
        # Shared destruction/cache behavior is recorded but is not a general requirement.
        require(row['unretained_control_never_submitted'] == (index == 1) and
                row['main_command_buffer_committed'] == (mode == 'execute' and retained),
                'unsafe negative submission or missing positive submission')
        if mode == 'execute':
            require(row['readback_encoded_before_submit'] == retained,
                    'readback must precede resource release at completion')
        count = 99 if mode == 'execute' and retained else 0
        seed = 0x7654 + 97 * index
        payload = bytearray()
        for i in range(count):
            payload.extend(struct.pack('<4I', ((seed * 1664525) ^ (i * 1013904223)) & 0xffffffff,
                                       i, 0x01010003, 33))
        expected_output = bytes([0xa5]) * 64 + payload + bytes([0xa5]) * (10368 - 64 - len(payload))
        output = root / f'outputs/case-{index}.output.bin'
        counter = root / f'outputs/case-{index}.counter.bin'
        require(output.read_bytes() == expected_output, f'raw output differs: {cases[index]}')
        require(counter.read_bytes() == bytes([0xa5]) * 64 + struct.pack('<I', count) +
                bytes([0xa5]) * 64, 'raw count/guard differs: ' + cases[index])
        require(row['actual_invocations'] == count and row['mismatches'] == 0,
                'host record disagrees with raw data')
        hashes[output.name] = sha(output)
        hashes[counter.name] = sha(counter)
    return {'status': 'PASS', 'mode': mode, 'lifetime_cases': 3,
            'GPU_submitted_user_buffers': 2 if mode == 'execute' else 0,
            'GPU_user_invocations': 198 if mode == 'execute' else 0,
            'correct_uint32_words': 792 if mode == 'execute' else 0,
            'ICB_and_scope_released_before_commit': True,
            'ended_encoders_released': True, 'default_private_retention': True,
            'unretained_private_release': True, 'unretained_control_never_submitted': True,
            'automatic_device_restore_before_commit': True, 'guard_mismatches': 0,
            'all_children_terminal': True, 'raw_files_verified': 6,
            'integration_level': 1, 'ICB_contract_complete': False,
            'performance_benchmark': False, 'system_modified': False,
            'host_executable_SHA256_rechecked': not portable,
            'portable_raw_verification_only': portable,
            'verifier_SHA256': sha(Path(__file__)), 'raw_SHA256': hashes,
            'scope': 'Two positive default-retained GPU cases and one never-submitted '
                     'unretained negative on a pinned native pipeline. Shared buffer '
                     'cache/destruction, concurrency and arbitrary pipelines remain unqualified.'}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--check-current-sources', action='store_true')
    p.add_argument('--portable', action='store_true',
                   help='Archive raw verification; omitted host binaries are not re-attested')
    args = p.parse_args()
    root = args.input.resolve()
    result = verify(root, args.check_current_sources, args.portable)
    (root / 'independent-verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'raw_SHA256'}, indent=2))
