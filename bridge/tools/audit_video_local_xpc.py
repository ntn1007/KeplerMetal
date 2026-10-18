#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independently recheck archived public-XPC controls; never execute a probe.

The two precisely characterized historical failures remain failures. They are
not converted into passing transport qualifications by an expected-exit rule.
"""
from pathlib import Path
import argparse
import datetime
import hashlib
import json
import struct
import subprocess

MASK = (1 << 32) - 1
SIZES = (1, 31, 32, 33, 257, 1024, 4096)


def load(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def oracle(word, seed, index):
    value = (word ^ seed) & MASK
    count = index % 31 + 1
    rotated = ((value << count) | (value >> (32-count))) & MASK
    return (rotated + index * 1664525 + 1013904223) & MASK


def provenance(root, build, reservation_root, expected_exit):
    inp, frozen = load(root / 'inputs.json'), load(build / 'inputs.json')
    manifest = load(root / 'execution/manifest.json')
    require(manifest['exit_code'] == expected_exit and not manifest['SIGKILL_requested']
            and not manifest['authoritative_ps_status']
            and manifest['GPU_reservation']['state'] == 'terminal', 'terminal manifest')
    require(Path(manifest['reservation_root']) == reservation_root, 'common host lease')
    current = subprocess.run(['ps', '-p', str(manifest['pid']), '-o', 'stat='],
                             capture_output=True, text=True, check=False)
    require(not current.stdout.strip(), 'historical PID currently exists; identity recheck required')
    require(sha(root / 'application') == sha(build / 'application')
            == inp['executable_SHA256'] == frozen['executable_SHA256']
            == manifest['original_binary_sha256'], 'executable pin')
    require(sha(root / 'execution/application') == manifest['signed_binary_sha256'], 'signed executable pin')
    require(inp['source_hashes'] == frozen['source_hashes']
            and inp['runtime_SHA256'] == frozen['runtime_SHA256'], 'source/runner manifest')
    for name, digest in inp['source_hashes'].items():
        require(sha(root / name) == sha(build / name) == digest, 'frozen source: ' + name)
    for name, digest in inp['runtime_SHA256'].items():
        require(sha(build / 'runtime' / name) == digest, 'runner hash: ' + name)
        field = {'run_sdk_host.py': 'launcher_SHA256', 'lab_gpu_reservation.py': 'reservation_module_SHA256'}[name]
        require(manifest[field] == digest, 'executed runner')
    require(manifest['arguments'] == [inp['mode'], str(root / 'outputs'), str(inp['seed'])], 'actual launch parameters')
    result = load(root / 'execution/execution.stdout')
    if (root / 'results.json').exists():
        require(result == load(root / 'results.json'), 'stdout/result identity')
    return inp, manifest, result


def primer(row, seed):
    require(row['kind'] == 'cancellation_primer' and row['sequence'] == 0xfedcba9876543210
            and row['seed'] == seed and row['input_word'] == 0x89abcdef
            and row['reply_word'] == oracle(0x89abcdef, seed, 0) and row['correct'], 'numeric cancellation primer')


def cancellation(row):
    require(row['kind'] == 'pending_reply_cancellation' and row['request_held']
            and row['reply_observed'] and row['reply_callbacks'] == 1
            and row['known_error'] and row['correct'], 'pending cancellation reply')


def case(root, build, reservation_root, failure=None):
    inp, manifest, result = provenance(root, build, reservation_root, 3 if failure else 0)
    seed, mode = inp['seed'], inp['mode']
    require(result['mode'] == mode and result['seed'] == seed
            and result['listener_name_was_NULL'] and result['accepted_connections']
            and result['client_invalid'] == 1 and result['context_destroyed']
            and result['live_contexts'] == 0, 'public connection/lifetime controls')
    for key in ['native_private_handler_called', 'public_video_API_called', 'hardware_video_execution_proved',
                'named_service_or_launchd_modified', 'system_modified', 'performance_benchmark']:
        require(result[key] is False, 'scope: ' + key)
    require(result['GPU_work'] == 0, 'CPU-only public-XPC control')
    words = primes = pending = 0
    if mode == 'cancel':
        if failure == 'pre_reply_unknown_PID':
            require(result['status'] == 'FAIL' and result['client_peer_PID'] == 0
                    and result['same_process'] is False and result['server_invalid'] == 1
                    and result['requests'] == 1 and len(result['trials']) == 1, 'exact V1 failure')
            cancellation(result['trials'][0]); pending = 1
        else:
            require(len(result['trials']) == 2 and result['requests'] == 2, 'primed cancellation geometry')
            primer(result['trials'][0], seed); cancellation(result['trials'][1]); primes = pending = 1
            require(result['same_process'] and result['client_peer_PID'] == manifest['pid'], 'primed peer identity')
            if failure == 'missing_server_invalid':
                require(result['status'] == 'FAIL' and result['server_invalid'] == 0
                        and not any(e['side'] == 'server' and e['kind'] == 'INVALID' for e in result['events']), 'exact V2 failure')
            else:
                require(result['status'] == 'PASS' and result['server_invalid'] == 1, 'qualified cancellation')
    else:
        require(not failure and result['status'] == 'PASS' and result['same_process']
                and result['client_peer_PID'] == manifest['pid'] and result['server_invalid'] == 1
                and result['requests'] == 7 and len(result['trials']) == 7, 'public RPC geometry')
        for trial, (row, count) in enumerate(zip(result['trials'], SIZES)):
            require(row['trial'] == trial and row['words'] == count and row['seed'] == seed
                    and row['sequence'] == 0xf000000000000000 + trial
                    and row['reply_callbacks'] == 1 and row['correct'], 'RPC parameters')
            require(row['input'] == 'input-%d.bin' % trial and row['reply'] == 'reply-%d.bin' % trial, 'result paths')
            original = [((seed + trial*971) & MASK) ^ ((i*747796405 + 2891336453) & MASK) for i in range(count)]
            expected = [oracle(value, seed, i) for i, value in enumerate(original)]
            require((root / 'outputs' / row['input']).read_bytes() == struct.pack('<%dI' % count, *original), 'dictionary copied input bytes')
            require((root / 'outputs' / row['reply']).read_bytes() == struct.pack('<%dI' % count, *expected), 'independent numeric reply')
            words += count
    return {'case': root.name, 'qualification_status': 'FAIL_PRESERVED' if failure else 'PASS',
            'failure': failure, 'PID': manifest['pid'], 'exit_code': manifest['exit_code'], 'mode': mode,
            'seed': seed, 'exact_uint32_words': words, 'primer_words': primes, 'pending_cancellations': pending,
            'manifest_SHA256': sha(root / 'execution/manifest.json'),
            'stdout_SHA256': sha(root / 'execution/execution.stdout'),
            'source_hashes': inp['source_hashes'], 'signed_executable_SHA256': manifest['signed_binary_sha256'],
            'started_at': manifest['started_at'], 'completed_at': manifest['completed_at']}


def audit(lab):
    root = lab.resolve() / 'bridge'; results = root / 'results'; rows = []
    for version, build_name in [(1, 'video-local-xpc-build-20261018'), (2, 'video-local-xpc-build-20261018-02')]:
        build = results / build_name
        for mode in ['sync', 'async', 'cancel']:
            name = 'video-local-xpc-%s-20261018' % mode if version == 1 else 'video-local-xpc-v2-%s-a-20261018' % mode
            failure = ('pre_reply_unknown_PID' if version == 1 else 'missing_server_invalid') if mode == 'cancel' else None
            rows.append(case(results / name, build, root, failure))
    for tag in ['a', 'b']:
        for mode in ['sync', 'async', 'cancel']:
            rows.append(case(results / ('video-local-xpc-v3-%s-%s-20261018' % (mode, tag)),
                             results / 'video-local-xpc-build-20261018-03', root))
    ordered = sorted(rows, key=lambda row: row['started_at'])
    for previous, following in zip(ordered, ordered[1:]):
        require(datetime.datetime.fromisoformat(previous['completed_at']) <= datetime.datetime.fromisoformat(following['started_at']), 'overlapping host processes')
    require(len({r['PID'] for r in rows}) == 12, 'fresh processes')
    return {'status': 'AUDIT_PASS_WITH_TWO_PRESERVED_QUALIFICATION_FAILURES', 'cases': rows,
            'terminal_processes': len(rows), 'passed_processes': 10, 'preserved_failed_processes': 2,
            'exact_uint32_words': sum(r['exact_uint32_words'] for r in rows),
            'primer_words': sum(r['primer_words'] for r in rows),
            'pending_cancellations': sum(r['pending_cancellations'] for r in rows),
            'new_V3_processes': 6, 'new_V3_exact_uint32_words': sum(r['exact_uint32_words'] for r in rows if '-v3-' in r['case']),
            'native_handler_qualification': 'NOT RUN by these public-XPC controls',
            'GPU_execution': False, 'system_modified': False, 'performance_benchmark': False}


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--lab-root', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True); args = p.parse_args()
    require(not args.out.exists(), 'new audit output required')
    result = audit(args.lab_root); args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'cases'}))


if __name__ == '__main__':
    main()
