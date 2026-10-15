#!/usr/bin/env python3
"""Portable raw-output oracle for the bounded CPU-recorded compute ICB probe.

No GPU execution. Derive active nodes/ranges from the declared experiment,
not from the probe's expected_active or passed fields. The result qualifies
only this public-selector subset on the pinned native pipeline.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(root, check_current, portable=False):
    inputs = json.loads((root / 'inputs.json').read_text())
    data = json.loads((root / 'results.json').read_text())
    manifest = json.loads((root / 'execution/manifest.json').read_text())
    for name, digest in inputs['source_hashes'].items():
        require(sha(root / name) == digest, f'frozen source differs: {name}')
        if check_current:
            folder = 'src' if name.startswith('Kepler') else 'tools'
            require(sha(Path(__file__).resolve().parents[1] / folder / name) == digest,
                    f'current source differs: {name}')
    library = sha(root / 'indirect_compute_probe.metallib')
    require(library == inputs['library_SHA256'] ==
            'b15f9b198ba326811f0a61f64fc32ac7cc185d04db63fa8e04f86075e8450a8d',
            'unqualified native library')
    require(manifest['exit_code'] == 0 and not manifest['SIGKILL_requested']
            and not manifest['authoritative_ps_status'], 'child not successfully terminal')
    if not portable:
        require(sha(root / 'cpu_icb_probe') == manifest['original_binary_sha256'],
                'original executable differs')
        require(sha(root / 'execution/cpu_icb_probe') == manifest['signed_binary_sha256'],
                'signed executable differs')
    commands = json.loads((root / 'commands.json').read_text())
    require(len(commands) == 2 and all(c['exit_code'] == 0 for c in commands),
            'build or observation failed')
    require(data['registry_id'] == 4294968458 and data['ICB_object_created']
            and data['scope_restored'], 'device/object/restoration differs')
    require(not data['ICB_contract_complete'] and not data['system_modified']
            and data['integration_level'] == 1, 'scope was overstated')
    expected_rejections = {'out_of_range', 'GPU_resource_identity',
                           'nonuniform_grid', 'descriptor_inheritance'}
    require({r['case'] for r in data['rejections']} == expected_rejections
            and all(r['rejected'] for r in data['rejections']), 'negative API controls differ')
    raw_hashes = {}
    for node in range(4):
        out = root / f'outputs/before-execute-{node}.output.bin'
        counter = root / f'outputs/before-execute-{node}.counter.bin'
        require(out.read_bytes() == bytes([0xa5]) * 10368,
                f'creation/setters changed output {node}')
        require(counter.read_bytes() == bytes([0xa5]) * 64 + bytes(4) + bytes([0xa5]) * 64,
                f'creation/setters changed counter {node}')
        raw_hashes[out.name] = sha(out)
        raw_hashes[counter.name] = sha(counter)

    events = data['events']
    factories = [e for e in events if e['operation'] == 'newIndirectCommandBuffer']
    materialized = [e for e in events if e['operation'] == 'materialize_CPU_command']
    executions = [e for e in events if e['operation'] == 'executeCommandsInBuffer']
    require(len(factories) == 2 and all(e['size'] == 5 and e['metadata_bytes'] == 2560
            for e in factories), 'factory slots/backing differ')
    require(events[0]['operation'] == 'scope_install' and
            not events[0]['capabilities_spoofed'] and
            events[-1]['operation'] == 'scope_restore' and
            events[-1]['device_class_restored'], 'scope lifecycle differs')
    mode = data['mode']
    require(mode in ('prepare', 'execute'), 'unknown mode')
    require(len(materialized) == (3 if mode == 'prepare' else 4),
            'unexpected materialization or failed reuse')
    # GPU non-execution during materialization is additionally tested by exact
    # post-submission counters in execute mode, not inferred from these event fields.
    require(all(e['requires_GPU_NOP_and_blit_preparation'] for e in materialized),
            'different preparation path')
    if mode == 'prepare':
        require(len(data['runs']) == len(executions) == 1, 'preparation run count differs')
        require(not data['runs'][0]['main_command_buffer_committed'],
                'preparation unexpectedly submitted')
        ranges = [(0, 5, [0, 2, 4])]
        invocations = words = output_nodes = 0
    else:
        require(len(data['runs']) == len(executions) == 7, 'GPU run count differs')
        active = [{0, 1, 2}, {1}, {0, 1, 2}, {0, 2}, {0, 2}, {0, 2, 3}, {2}]
        ranges = [(0, 5, [0, 2, 4]), (2, 1, [2]), (0, 5, [0, 2, 4]),
                  (0, 5, [0, 4]), (0, 5, [0, 4]), (0, 5, [0, 2, 4]), (4, 1, [4])]
        sizes = [(1, 32), (3, 33), (5, 128), (3, 33)]
        invocations = words = output_nodes = 0
        for trial, run in enumerate(data['runs']):
            require(run['trial'] == trial and run['command_status'] == 4 and
                    run['GPU_user_kernel_execution'], f'command incomplete: trial {trial}')
            require(run['selected_buffer'] == ('copy' if trial in (4, 6) else 'source'),
                    'copy/source selection differs')
            require(len(run['outputs']) == 4, 'missing output node')
            for node, row in enumerate(run['outputs']):
                groups, local = sizes[node]
                n = groups * local
                seed = 0x1234 + 101 * node + 37 * trial
                out = root / f'outputs/trial-{trial}-node-{node}.output.bin'
                counter = root / f'outputs/trial-{trial}-node-{node}.counter.bin'
                if node in active[trial]:
                    values = []
                    for i in range(n):
                        values.extend([((seed * 1664525) ^ (i * 1013904223)) & 0xffffffff,
                                       i, groups | 0x01010000, local])
                    payload = struct.pack('<' + 'I' * len(values), *values)
                    expected = bytes([0xa5]) * 64 + payload + bytes([0xa5]) * (10368 - 64 - len(payload))
                    expected_count = n
                    invocations += n
                    words += len(values)
                    output_nodes += 1
                else:
                    expected = bytes([0xa5]) * 10368
                    expected_count = 0
                require(out.read_bytes() == expected, f'GPU output differs: trial{trial}/node{node}')
                require(counter.read_bytes() == bytes([0xa5]) * 64 +
                        struct.pack('<I', expected_count) + bytes([0xa5]) * 64,
                        f'GPU count/guards differ: trial{trial}/node{node}')
                require(row['node'] == node and row['actual_invocations'] == expected_count,
                        'JSON counter disagrees with raw data')
                raw_hashes[out.name] = sha(out)
                raw_hashes[counter.name] = sha(counter)
        require(len([e for e in events if e['operation'] == 'CPU_reset']) == 1,
                'missing reset control')
        copies = [e for e in events if e['operation'] == 'CPU_snapshot_copy']
        require(len(copies) == 1 and not copies[0]['GPU_timeline_copy'],
                'missing CPU snapshot copy or overstated blit support')
    for event, (location, length, indices) in zip(executions, ranges):
        require((event['location'], event['length'], event['executed_indices']) ==
                (location, length, indices), 'executed range/slots differ')
        evidence = event['evidence']
        require(evidence['raw_packet_copies'] == len(indices) and
                evidence['native_preparation_GPU_dispatches'] == 0 and
                evidence['command_bytes'] == len(indices) * 464 and
                not evidence['system_modified'], 'native emission differs')
    return {'status': 'PASS', 'mode': mode, 'CPU_ICB_public_selector_subset': True,
            'CPU_creation_and_setters_zero_user_invocations_raw_checked': True,
            'submitted_user_command_buffers': 7 if mode == 'execute' else 0,
            'output_node_results': 28 if mode == 'execute' else 0,
            'active_node_results': output_nodes, 'user_GPU_invocations': invocations,
            'correct_uint32_words': words, 'guard_mismatches': 0,
            'raw_files_verified': len(raw_hashes), 'materialized_commands': len(materialized),
            'scope_restored': True, 'all_children_terminal': True,
            'ICB_contract_complete': False, 'GPU_generated_ICB': False,
            'GPU_timeline_copy_reset': False, 'integration_level': 1,
            'performance_benchmark': False, 'system_modified': False,
            'host_executable_SHA256_rechecked': not portable,
            'portable_raw_verification_only': portable,
            'verifier_SHA256': sha(Path(__file__)), 'raw_SHA256': raw_hashes,
            'scope': 'Pinned buffer-only native consume_grid pipeline and serial encoder. '
                     'CPU state/reset/snapshot copy; no resourceID export, inherited states, '
                     'render ICB or ordinary-app integration qualification.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--check-current-sources', action='store_true')
    parser.add_argument('--portable', action='store_true',
                        help='Archive raw verification; omitted host binaries are not re-attested')
    args = parser.parse_args()
    root = args.input.resolve()
    result = verify(root, args.check_current_sources, args.portable)
    (root / 'independent-verification.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'raw_SHA256'}, indent=2))
