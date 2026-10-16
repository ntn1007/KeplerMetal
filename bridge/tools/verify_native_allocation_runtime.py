#!/usr/bin/env python3
"""Recompute frozen native-allocation API evidence without GPU execution.

This milestone verifier requires private, locally generated fixtures. It does
not claim that a source export or a different archive inherits these results.
"""
from pathlib import Path
import argparse
import json

from qualify_native_reserve import verify_case, under_results
from verify_native_control_reserve import terminal, load, sha, require
from verify_native_allocation_common import allocation_proof, verify_concurrency, verify_coexist
from verify_local_memory import verify as verify_local

ROOT = Path(__file__).resolve().parents[1]
PROGRESS = ROOT / 'results/native-allocation-runtime-progress-20261016'
LIBRARY = ROOT / 'results/native-allocation-runtime-build-20261016-04'
LIBRARY_HASH = '5636b0d0d158fc985bf9b1df5fd0e16b91909a9a6f48423c175272b7fe4ddb67'


def matrix(path, suite, library):
    rows = load(path)['cases']; status = load(suite / 'status.json')
    history = load(suite / 'history.json'); lm = load(library / 'manifest.json')
    require(status['status'] == 'PASS' and status['matrix_SHA256'] == sha(path)
            and status['cases'] == len(rows) == len(history), 'matrix completion')
    checked = []
    for i, (row, recorded) in enumerate(zip(rows, history)):
        require(recorded['index'] == i and recorded['exit_code'] == 0
                and all(recorded[k] == v for k, v in row.items()), 'matrix history')
        outcome = verify_case(row)
        require(outcome == recorded['verification'], 'numeric verification changed')
        root, build = under_results(row['result']), under_results(row['build'])
        inp = load(build / 'inputs.json'); d = load(root / 'results.json')
        require(inp['static_library_SHA256'] == lm['static_library_SHA256']
                and inp['library_manifest_SHA256'] == sha(library / 'manifest.json'), 'linked archive')
        manifest = load(root / 'assets/native-allocation-manifest.json')
        entry = manifest['certificates'][d['function']]
        require(sha(root / 'assets' / entry['file']) == entry['SHA256'], 'certificate manifest')
        proof = allocation_proof(d['import'], root / 'assets/control_flow.metallib',
                                 root / 'assets' / entry['file'])
        require(d['import']['legacy_arguments_match_certificate']
                and d['import']['factory_autorelease_pool_drained'], 'factory contract')
        if inp['lifetime_probe']:
            require(d['import']['caller_library_overwritten']
                    and d['import']['caller_certificate_overwritten'], 'lifetime mutation')
        checked.append({'result': row['result'], 'expect': row['expect'],
                        'lifetime': inp['lifetime_probe'], 'proof': proof, **outcome})
    return checked


def refusals():
    suite = ROOT / 'results/native-allocation-contract-suite-20261016-04'
    plan = load(suite / 'planned-cases.json'); history = load(suite / 'history.json')
    require(load(suite / 'complete.json')['status'] == 'PASS'
            and len(history) == len(plan['modes']) == 16, 'refusal completion')
    build = under_results(plan['build']); output = []
    for row, mode in zip(history, plan['modes']):
        root = under_results(row['result_root']); inp = terminal(root, ROOT, build)
        d = load(root / 'results.json'); p = d['import']
        require(row['exit_code'] == 0 and row['mode'] == mode == d['mode']
                and inp == load(build / 'inputs.json') and inp['static_library_SHA256'] == LIBRARY_HASH,
                'refusal provenance')
        require(d['status'] == 'PASS' and d['rejection_verified'] and not d['pipeline_returned']
                and d['error'] and d['constructor_restored'] and d['native_recovery_pipeline_created']
                and d['GPU_command_buffers'] == d['kernel_dispatches'] == 0 and d['runs'] == []
                and d['registry_id'] == 4294968458 and not d['system_modified'], 'refusal result')
        phase = ('constructor' if mode in {'code_hash', 'gpr', 'static_word', 'function'}
                 else 'missing_callback' if mode == 'missing_function' else 'gate')
        require(d['phase'] == phase, 'refusal phase')
        if phase == 'constructor':
            require(p['gate_accepted'] and p['constructor_entered'] and p['calls'] == 1
                    and len(p['events']) == 1 and not p['contract_verified']
                    and p['constructor_restored'] and not p['events'][0]['certificate_matches']
                    and 'only_metadata_words9_11_changed' not in p['events'][0], 'late refusal')
        elif phase == 'missing_callback':
            require(p['gate_accepted'] and not p['constructor_entered'] and p['calls'] == 0
                    and p['constructor_restored'] and not p['contract_verified'], 'missing callback')
        else:
            require(not p['gate_accepted'] and not p['constructor_entered'], 'early refusal')
        output.append({'mode': mode, 'phase': phase, 'status': 'PASS',
                       'manifest_SHA256': sha(root / 'execution/manifest.json')})
    return output


def verify():
    start = load(PROGRESS / 'start.json'); lm = load(LIBRARY / 'manifest.json')
    require(sha(LIBRARY / 'libKeplerMetal.a') == lm['static_library_SHA256'] == LIBRARY_HASH
            and lm['all_runtime_modules_rebuilt'] and not lm['reused_object_SHA256']
            and len(lm['object_SHA256']) == 6, 'runtime build')
    for name, digest in lm['source_SHA256'].items():
        require(sha(LIBRARY / name) == digest and sha(ROOT / name) == digest, 'runtime source: ' + name)
    for name, digest in lm['object_SHA256'].items():
        require(sha(LIBRARY / name) == digest, 'runtime object')
    checked = matrix(PROGRESS / 'numeric-matrix-04.json',
                     ROOT / 'results/native-allocation-api-numeric-suite-20261016-04', LIBRARY)
    positives = [r for r in checked if r['expect'] == 'numeric_pass']
    missing = [r for r in checked if r['expect'] == 'no_dispatch']
    require(len(positives) == 19 and len(missing) == 2
            and len({r['native_code_SHA256'] for r in positives}) == 17, 'profile coverage')
    contracts = refusals()
    concurrency = verify_concurrency(ROOT / 'results/native-allocation-concurrency-20261016-04',
                                     ROOT / 'results/native-allocation-concurrency-build-20261016-04')
    coexist_build = ROOT / 'results/native-allocation-coexist-build-20261016-04'
    coexist = verify_coexist(ROOT / 'results/native-allocation-coexist-execute-20261016-04', coexist_build)
    negative = verify_coexist(ROOT / 'results/native-allocation-coexist-negative-20261016-04', coexist_build)
    local_build = ROOT / 'results/native-allocation-local-client-build-20261016-04'; local = []
    for name in ['local1024', 'pressure96', 'pressure32_forced_spill']:
        root = ROOT / 'results' / ('native-allocation-regression-nak-' + name + '-20261016-04')
        inp = terminal(root, ROOT, local_build)
        require(inp['static_library_SHA256'] == LIBRARY_HASH, 'local archive')
        proof = verify_local(root); proof.pop('files_SHA256'); local.append(proof)
    for result in [concurrency, coexist, negative]:
        require(result['static_library_SHA256'] == LIBRARY_HASH, 'common archive')
    # Preserve the real concurrency failure before the adapter restoration fix.
    failed = ROOT / 'results/native-allocation-concurrency-20261016'
    fm = load(failed / 'execution/manifest.json'); fd = load(failed / 'execution/execution.stdout')
    require(fm['exit_code'] == 3 and not fm['SIGKILL_requested'] and not fm['authoritative_ps_status']
            and fm['GPU_reservation']['state'] == 'terminal' and fd['runs'] == []
            and fd['constructor_restored'] and not fd['CAS']['constructor_restored']
            and fd['CAS']['native_import']['contract_verified'], 'preserved concurrency failure')
    failed_local = ROOT / 'results/native-allocation-regression-nak-pressure96_forced_spill-20261016-04'
    fl = load(failed_local / 'execution/manifest.json')
    require(fl['exit_code'] == -6 and not fl['SIGKILL_requested'] and not fl['authoritative_ps_status']
            and fl['GPU_reservation']['state'] == 'terminal'
            and (failed_local / 'execution/execution.stdout').read_bytes() == b''
            and 'data parameter is nil' in (failed_local / 'execution/execution.stderr').read_text(),
            'preserved unavailable-profile harness failure')
    for row in start['system_before']:
        require(sha(row['path']) == row['SHA256'], 'system changed: ' + row['path'])
    require(len(start['system_before']) == 83
            and sha('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist') == start['OCLP_SHA256'],
            'system/OCLP baseline')
    native_trials = sum(r['trials'] for r in positives)
    no_dispatch = sum(r['trials'] for r in missing)
    total_cb = native_trials + no_dispatch + concurrency['GPU_command_buffers'] + coexist['total_user_GPU_command_buffers'] + sum(r['trials'] for r in local)
    values = sum(r['exact_uint32_results'] for r in positives) + concurrency['exact_uint32_results'] + coexist['CAS']['correct_uint32_words'] + sum(r['exact_uint32_results'] for r in coexist['postludes'] + local)
    guards = sum(r['guard_bytes'] for r in checked) + concurrency['guard_bytes'] + coexist['CAS']['guard_bytes_verified'] + sum(r['guard_bytes'] for r in coexist['postludes'] + local)
    return {'status': 'PASS', 'scope': 'Pinned native allocation API in common MRC runtime; adapted application only',
            'base_commit': start['base_commit'], 'library_SHA256': LIBRARY_HASH,
            'source_SHA256': lm['source_SHA256'], 'cases': checked, 'refusals': contracts,
            'concurrency': concurrency, 'coexistence': coexist, 'CAS_refusals': negative,
            'local_regressions': local, 'positive_native_trials': native_trials,
            'distinct_native_profiles': 17, 'lifetime_native_trials': sum(r['trials'] for r in positives if r['lifetime']),
            'no_dispatch_trials': no_dispatch, 'total_user_GPU_command_buffers': total_cb,
            'total_compute_dispatches': total_cb - no_dispatch, 'total_exact_uint32_results': values,
            'total_guard_bytes': guards, 'correct_CAS_operations': concurrency['native_and_CAS_kernels'][1]['correct_CAS_operations'] + coexist['CAS']['correct_CAS_operations'],
            'system_files_unchanged': 83, 'OCLP_unchanged': True,
            'preserved_failure_manifests': {str(p.relative_to(ROOT)): sha(p) for p in [failed / 'execution/manifest.json', failed_local / 'execution/manifest.json']},
            'new_M1_executions': 0, 'Qwen_job_ids': [], 'performance_benchmark': False,
            'full_objective_complete': False,
            'limits': ['17 pinned profiles; reserve4096 is tested, no general allocation rule',
                       'Constructor payload identity is not resident instruction readback',
                       'Concurrent factory creation tested; actual GPU kernels serialized',
                       'Coexistence descriptor prelude creates a PSO, no descriptor producer dispatch',
                       'Full historical 296-trial library/function suite NOT RUN on this archive',
                       'Public seven-object archive has separate artifact-specific qualification',
                       'No installed-driver change, general Metal3/4 support or speedup claim']}


def verify_public(library):
    library = library.resolve(); lm = load(library / 'manifest.json')
    require(lm['status'] == 'PASS' and not lm['GPU_execution']
            and not lm['historical_qualification_inherited'] and lm['architecture'] == 'x86_64'
            and len(lm['object_SHA256']) == 7
            and sha(library / 'libKeplerMetal.a') == lm['static_library_SHA256'], 'public build')
    lab = load(LIBRARY / 'manifest.json')
    for name, digest in lm['source_SHA256'].items():
        require(sha(library / 'src' / name) == digest, 'public frozen source')
        if 'src/' + name in lab['source_SHA256']:
            require(digest == lab['source_SHA256']['src/' + name], 'public/lab source identity')
    for name, digest in lm['object_SHA256'].items():
        require(sha(library / name) == digest, 'public object')
    commands = load(library / 'commands.json')
    require(all(r['exit_code'] == 0 for r in commands)
            and any(r['label'] == 'cpu-link-check' for r in commands), 'public build/link commands')
    cases = matrix(PROGRESS / 'public-matrix.json', ROOT / 'results/native-allocation-public-numeric-suite-20261016', library)
    require(len(cases) == 3 and all(r['expect'] == 'numeric_pass' for r in cases)
            and sum(r['trials'] for r in cases if r['lifetime']) == 24
            and max(r['native_frame'] for r in cases) == 4656
            and max(r['native_code_bytes'] for r in cases) == 104000, 'public smoke coverage')
    concurrency = verify_concurrency(ROOT / 'results/native-allocation-public-concurrency-20261016',
                                     ROOT / 'results/native-allocation-public-concurrency-build-20261016')
    require(concurrency['static_library_SHA256'] == lm['static_library_SHA256'], 'public concurrency archive')
    return {'status': 'PASS', 'scope': 'Artifact-specific public seven-object archive smoke',
            'library_SHA256': lm['static_library_SHA256'], 'library_manifest_SHA256': sha(library / 'manifest.json'),
            'SDK': lm['SDK'], 'architecture': lm['architecture'], 'runtime_objects': 7,
            'same_common_runtime_source_as_lab': True, 'cases': cases, 'concurrency': concurrency,
            'native_compute_trials': sum(r['trials'] for r in cases),
            'lifetime_trials': sum(r['trials'] for r in cases if r['lifetime']),
            'total_user_GPU_command_buffers': sum(r['trials'] for r in cases) + concurrency['GPU_command_buffers'],
            'total_exact_uint32_results': sum(r['exact_uint32_results'] for r in cases) + concurrency['exact_uint32_results'],
            'total_guard_bytes': sum(r['guard_bytes'] for r in cases) + concurrency['guard_bytes'],
            'full_lab_matrix': 'NOT RUN', 'historical_qualification_inherited': False,
            'performance_benchmark': False, 'full_objective_complete': False}


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--public-library', type=Path, help='Check the separate public archive smoke')
    a = p.parse_args(); out = a.out.resolve(); out.relative_to(ROOT / 'results')
    data = verify_public(a.public_library) if a.public_library else verify()
    with out.open('x') as f: json.dump(data, f, indent=2); f.write('\n')
    print(json.dumps({k:v for k,v in data.items() if k not in {'source_SHA256','cases','refusals','concurrency','coexistence','CAS_refusals','local_regressions'}}, indent=2))
