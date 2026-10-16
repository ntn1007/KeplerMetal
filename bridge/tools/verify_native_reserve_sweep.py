#!/usr/bin/env python3
"""Classify every result without mapping numeric defects to successful computation."""
from pathlib import Path
import argparse
import json
import struct

from verify_native_control_reserve import terminal, require, load, sha, DRIVER
from verify_control_flow import result as cpu_result

ROOT = Path(__file__).resolve().parents[1]


def verify(root, build, native, observations, reserve, depth, reservation_root=None,
           expected_variant='nested'):
    inp = terminal(root, reservation_root or ROOT, build)
    require(inp == load(build / 'inputs.json') and inp['reserve_mode'] == str(reserve)
            and inp['native_build_inputs_SHA256'] == sha(native / 'inputs.json')
            and inp['observations_SHA256'] == sha(observations / 'observations.json')
            and inp['source_generator_SHA256'] == sha(build / 'builder.py')
            and inp['module_object_SHA256'] == sha(build / 'reserve.o'), 'experiment provenance')
    d = load(root / 'results.json'); proof = d['import']; config = load(root / 'assets/control_flow_config.json')
    require(expected_variant in ['nested', 'reload_bounds']
            and expected_variant == load(native / 'inputs.json').get('variant', 'nested')
            == config['variant'], 'explicit nested-equivalent oracle variant')
    require(d['depth'] == depth and d['function'] == d['mode'] == 'depth' + str(depth)
            and d['variant'] == expected_variant and d['native_reference'] and not d['program_replaced']
            and not d['CPU_expected_answers_uploaded'] and not d['system_modified'] and not d['performance_benchmark']
            and d['driver_SHA256'] == DRIVER and d['registry_id'] == 4294968458, 'experiment target')
    require(proof['contract_verified'] and proof['constructor_restored'] and proof['calls'] == 1
            and len(proof['events']) == 1 and not proof['native_program_replaced'], 'constructor result')
    e = proof['events'][0]; w = e['actual_metadata_words']
    row = next(r for r in load(observations / 'observations.json')['records'] if r['function'] == d['function'])
    require(config['certificates'][d['function']]['metadata_words'] == row['metadata_words']
            and all(w[i] == row['metadata_words'][i] for i in range(58) if i not in [2, 4])
            and config['control_reserve'] == reserve, 'native metadata pins')
    for flag in ['certificate_matches', 'parsed', 'metadata_match', 'code_match',
                 'only_metadata_words9_11_changed', 'native_code_identical',
                 'native_code_identical_after_constructor', 'payload_unchanged_after_constructor',
                 'decoded_contract_verified']:
        require(e[flag] is True, 'constructor evidence: ' + flag)
    require(e['actual_code_SHA256'] == e['post_constructor_code_SHA256'] == row['code_SHA256']
            == sha(observations / d['function'] / 'capture/native.sass')
            and e['code_bytes'] == row['code_bytes'] and e['native_frame'] == w[12]
            and e['old_control'] == w[11] <= reserve == e['new_control'] == e['requested_reserve']
            and e['decoded_allocation_word40'] == e['expected_allocation_word40']
            == ((w[12] + 15) & ~15) * 64 + reserve + 512, 'allocation/code identity')
    counts = [1,31,32,33,64,128,256,512,1024,99,256,2048]
    locals_ = [1,31,32,33,64,128,256,512,1024,33,64,1024]
    require(len(d['runs']) == 12, 'trial count'); trials = []; files = {}
    for trial, r in enumerate(d['runs']):
        n, seed, reserved = counts[trial], 0x13579 + trial * 971, trial % 3
        require(r['trial'] == trial and r['threads'] == n and r['local'] == locals_[trial]
                and r['groups'] * r['local'] == n and r['seed'] == seed and r['reserved'] == reserved
                and r['stride'] == 129 and r['command_status'] == 4 and r['kernel_dispatches'] == 1,
                'dispatch record')
        want_input = bytearray(b'\xa5' * (256 + n * 129 * 4))
        for i in range(n * 129): struct.pack_into('<I', want_input, 128 + 4*i, ((i*1664525+1013904223)&0xffffffff)^seed)
        input_path = root / 'outputs' / r['input_file']; output_path = root / 'outputs' / r['output_file']
        got = output_path.read_bytes(); expected = bytearray(b'\xa5' * (256 + n * 16))
        require(r['input_bytes'] == len(want_input) and input_path.read_bytes() == want_input
                and r['output_bytes'] == len(expected) == len(got)
                and got[:128] == got[-128:] == b'\xa5'*128, 'input/guards')
        matches = unchanged = other = witnesses = 0
        for gid in range(n):
            want = cpu_result(depth, gid, seed, reserved); values = struct.unpack_from('<4I', got, 128 + gid*16)
            for value, answer in zip(values, want):
                if value == answer: matches += 1
                elif value == 0xa5a5a5a5: unchanged += 1
                else: other += 1
            witnesses += int(values[3] == want[3])
        status = 'PASS' if matches == n*4 else 'UNCHANGED_OUTPUT' if unchanged == n*4 else 'NUMERICAL_FAILURE'
        trials.append({'trial': trial, 'threads': n, 'local': r['local'], 'status': status,
                       'exact_uint32_results': matches, 'unchanged_wrong_words': unchanged,
                       'other_wrong_words': other, 'invocation_witnesses': witnesses})
        for p in [input_path, output_path]: files[p.name] = sha(p)
    return {'observation_status': 'VERIFIED', 'numerical_status': 'PASS' if all(t['status']=='PASS' for t in trials) else 'FAIL',
            'depth': depth, 'reserve': reserve, 'original_word11': w[11], 'native_code_SHA256': row['code_SHA256'],
            'native_frame': w[12], 'native_program_unchanged': True, 'constructor_restored': True,
            'GPU_command_buffers': 12, 'kernel_dispatches': 12, 'guard_bytes': 6144, 'trials': trials,
            'exact_uint32_results': sum(t['exact_uint32_results'] for t in trials),
            'wrong_uint32_results': sum(t['unchanged_wrong_words']+t['other_wrong_words'] for t in trials),
            'files_SHA256': files, 'performance_benchmark': False, 'full_objective_complete': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    for name in ['root', 'build', 'native', 'observations', 'out']: p.add_argument('--'+name, type=Path, required=True)
    for name in ['reserve', 'depth']: p.add_argument('--'+name, type=int, required=True)
    p.add_argument('--variant', choices=['nested', 'reload_bounds'], default='nested',
                   help='Explicit source variant; reload_bounds preserves the immutable-input nested oracle')
    a = p.parse_args(); proof = verify(a.root.resolve(), a.build.resolve(), a.native.resolve(), a.observations.resolve(), a.reserve, a.depth,
                                    expected_variant=a.variant)
    out=a.out.resolve();out.relative_to(ROOT/'results')
    with out.open('x') as f: json.dump(proof, f, indent=2); f.write('\n')
    print(json.dumps({k:v for k,v in proof.items() if k not in ['files_SHA256','trials']}, indent=2))
