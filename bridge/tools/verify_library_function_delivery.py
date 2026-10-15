#!/usr/bin/env python3
"""Audit ordinary library/function integration using frozen artifacts and CPU oracles."""
from pathlib import Path
import argparse
import hashlib
import json
from verify_command_ir_dataflow import verify as numeric

ROOT = Path(__file__).resolve().parents[1]
def load(path): return json.loads(Path(path).read_text())
def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def terminal(root):
    m = load(root / 'execution/manifest.json')
    assert m['exit_code'] == 0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
    assert m['GPU_reservation']['state'] == 'terminal'
    i = load(root / 'inputs.json')
    assert sha(root / 'application') == i['executable_SHA256'] == m['original_binary_sha256']
    for n, h in i['source_hashes'].items(): assert sha(root / n) == h
    for n, h in i.get('assets_SHA256', {}).items(): assert sha(root / 'assets' / n) == h
    return i

def verify():
    lib = ROOT / 'results/library-function-runtime-build-20261015-03'
    lm = load(lib / 'manifest.json'); pin = sha(lib / 'libKeplerMetal.a')
    assert pin == lm['static_library_SHA256']
    for name, h in lm['source_SHA256'].items():
        assert sha(lib / name) == h
        source = ROOT / name
        if not source.exists():
            assert name == 'src/KeplerFP64Programs.inc'
            source = ROOT / 'results/gpu-generated-bindings-sdk-build-20261014-02/KeplerMetalSDK/src/KeplerFP64Programs.inc'
        assert sha(source) == h
    native = ROOT / 'results/native-library-function-probe-20261015'
    terminal(native); nd = load(native / 'results.json')
    assert len(nd['runs']) == 20 and not nd['user_GPU_command_buffers'] and not nd['experimental_runtime']
    assert all(x['created'] and not x['error'] and not x['exception']
               and x['library_class'] == '_MTLLibrary' and x['library_instance_bytes'] == 64
               and x['function_class'] == '_MTLFunctionInternal' and x['function_instance_bytes'] == 400
               and x['function_constants'] == 0 and x['callbacks'] == (1 if x['kind'] in [8, 9] else 0)
               for x in nd['runs'])
    cpu = ROOT / 'results/library-function-inputs-probe-20261015'
    assert terminal(cpu)['static_library_SHA256'] == pin
    cd = load(cpu / 'results.json')
    assert len(cd['runs']) == 82 and all(x['PASS'] for x in cd['runs'])
    assert cd['scope_released_with_reflection_alive'] and not cd['command_buffers_submitted']
    rejected = [x for x in cd['runs'] if x['kind'] == 'library_registration_rejection']
    assert len(rejected) == 5 and all(x['native_imports'] == 0 for x in rejected)
    copied = next(x for x in cd['runs'] if x['kind'] == 'library_registration_inputs_copied')
    assert copied['native_imports'] == 6 and copied['duplicate_refused_without_import']
    assert copied['all_caller_inputs_mutated_after_registration']
    factories = [x for x in cd['runs'] if x['kind'] == 'automatic_library_function']
    assert len(factories) == 30 and sum(x['expected_refusal'] for x in factories) == 3
    lifecycle = []
    for mode in ['library_lifetime', 'pending']:
        r = ROOT / 'results' / ('library-function-' + mode + '-20261015')
        assert terminal(r)['static_library_SHA256'] == pin
        d = load(r / 'results.json')
        assert len(d['runs']) == 49 and all(x['PASS'] for x in d['runs'])
        assert d['scope_released_with_reflection_alive'] and not d['command_buffers_submitted']
        lifecycle.extend(x for x in d['runs'] if x['kind'] in ['library_scope_release_live_objects', 'pending_scope_release'])
    assert len(lifecycle) == 2
    legacy = ROOT / 'results/library-function-legacy-contract-probe-20261015'
    assert terminal(legacy)['static_library_SHA256'] == pin
    ld = load(legacy / 'results.json')
    assert len(ld['runs']) == 93 and all(x['PASS'] for x in ld['runs'])
    assert ld['scope_released_with_reflection_alive'] and not ld['command_buffers_submitted']

    client = ROOT / 'results/library-function-reception-client-build-20261015-06'
    assert load(client / 'inputs.json')['source_generator_SHA256'] == sha(ROOT / 'tools/build_pipeline_contract_reception_client.py')
    text = (client / 'command_ir_dataflow_client.mm').read_text()
    for forbidden in ['adaptComputeEncoder:', 'newCommandIRFunctionWithLibraryData:', 'registerCommandIRProducerForFunction:']:
        assert forbidden not in text
    assert text.index('id<MTLLibrary>unregistered=') < text.index('if(!receptionRegisterLibrary(')
    cases = []
    for folder, family in [('library-function-pipeline-qualification-20261015', 'pipeline'),
                           ('library-function-factory-qualification-20261015', 'library_function')]:
        suite = ROOT / 'results' / folder
        assert load(suite / 'status.json')['status'] == 'PASS'
        for h in load(suite / 'history.json'):
            assert h['exit_code'] == 0
            if h['phase'] != 'CPU': continue
            root = Path(h['result']); inp = terminal(root); d = load(root / 'results.json'); v = numeric(root)
            assert inp['static_library_SHA256'] == pin and inp['library_registration'] and inp['automatic_encoders']
            assert sha(root / 'command_ir_dataflow_client.mm') == sha(client / 'command_ir_dataflow_client.mm')
            for helper in ['PipelineFactoryReception.inc', 'QueueFactoryReception.inc', 'LibraryFunctionReception.inc']:
                assert sha(root / helper) == sha(client / helper) == sha(ROOT / 'tools' / helper)
            l = h['library_factory'] if family == 'library_function' else 0
            f = h['function_factory'] if family == 'library_function' else 0
            p = 5 if family == 'library_function' else h['factory_kind']
            q, e = (1, 4) if family == 'library_function' else (0, 0)
            assert d['factory_kind'] == p and d['queue_factory_kind'] == q and d['encoder_factory_kind'] == e
            assert d['ordinary_library_function_factories'] and d['manual_function_registration_calls'] == 0
            assert d['manual_compute_adaptation_calls'] == 0 and d['native_control_before_library_registration']
            assert d['ordinary_pipeline_passthrough'] and d['unregistered_native_failure_preserved']
            assert d['producer_registration_refusals'] == 4 and d['registration_refusals_scope'] == 'library'
            evidence = d['library_function_evidence']
            assert evidence['library_factory'] == l and evidence['function_factory'] == f
            assert evidence['callbacks'] == (1 if f in [7, 8] else 0) and evidence['function_constants'] == 0
            assert evidence['returned_name'] == ('alias_' if f == 6 else '') + evidence['source_name']
            events = d['function_events']; registrations = [x for x in events if x['operation'] == 'register_IRv2_library']
            assert len(registrations) == 1 and registrations[0]['prepared_native_pipelines'] == 6
            assert any(x['operation'] == 'automatic_IRv2_function' and x['source_function'] == evidence['source_name']
                       and x['returned_function'] == evidence['returned_name'] and x['pipeline_imports_during_lookup'] == 0 for x in events)
            assert d['factory_evidence']['max_threads'] == (32 if p in [2, 5] else 1024)
            assert d['factory_evidence']['requested_max_threads'] == (32 if p in [2, 5] else 0)
            cases.append({'family': family, 'library_factory': l, 'function_factory': f, 'pipeline_factory': p,
                          'queue_factory': q, 'encoder_factory': e, 'mode': h['mode'],
                          **{k: v[k] for k in ['trials', 'exact_uint32_results', 'consumer_invocations', 'guard_bytes']}})
    assert len(cases) == 74
    reference = ROOT / 'results/library-function-M1-return-20261015-06/Reference'
    returned = load(reference / 'REFERENCE_RETURN.json')
    for row in returned['files']: assert sha(reference / row['path']) == row['SHA256']
    for name in ['command_ir_dataflow_client.mm', 'PipelineFactoryReception.inc', 'QueueFactoryReception.inc', 'LibraryFunctionReception.inc']:
        assert sha(reference / name) == sha(client / name)
    matches = []
    for mode in ['no_producer', 'barrier', 'no_consumer']:
        assert numeric(reference / 'results' / mode)['status'] == 'PASS'
        d = load(reference / 'results' / mode / 'results.json')
        assert not d['native_control_before_library_registration']
        assert d['library_function_evidence']['function_factory'] == 6 and d['library_function_evidence']['library_factory'] == 2
        target = ROOT / 'results' / ('library-function-factories-20261015-l2-f6-barrier' if mode == 'barrier'
                                    else 'library-function-final-20261015-k5-' + mode)
        for trial in d['runs']:
            for name in ['input', 'dummySrc', 'stage0', 'stage1', 'stage2', 'counter', 'dummyCounter', *[f'dummy{i}' for i in range(6)]]:
                file = trial['files'][name]
                assert sha(reference / 'results' / mode / 'outputs' / file) == sha(target / 'outputs' / file)
                matches.append({'mode': mode, 'file': file, 'SHA256': sha(target / 'outputs' / file)})
    assert len(matches) == 156
    baseline = load(ROOT / 'results/pipeline-contract-runtime-progress-20261015/final-verification.json')
    assert len(baseline['system_files']) == 83
    for row in baseline['system_files']: assert sha(row['path']) == row['baseline_SHA256']
    assert sha('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist') == baseline['OCLP_SHA256']
    failed = ROOT / 'results/library-function-smoke-20261015-04'
    fm = load(failed / 'execution/manifest.json'); fd = load(failed / 'execution/execution.stdout')
    assert fm['exit_code'] == 3 and not fm['authoritative_ps_status'] and not fm['SIGKILL_requested']
    assert fd['check'] == 10 and not fd['runs'] and not list((failed / 'outputs').iterdir())
    assert any(x['operation'] == 'automatic_IRv2_function' and x['returned_function'] == 'encode_dataflow_barrier'
               for x in fd['library_events'])
    public = ROOT.parents[1] / 'publication/KeplerMetal/build/library-function-source-20261015'
    pm = load(public / 'manifest.json'); public_pin = sha(public / 'libKeplerMetal.a')
    assert pm['status'] == 'PASS' and len(pm['object_SHA256']) == 7 and public_pin == pm['static_library_SHA256']
    for name, h in lm['source_SHA256'].items(): assert sha(public / name) == h
    smoke = ROOT / 'results/library-function-public-source-smoke-20261015'
    assert terminal(smoke)['static_library_SHA256'] == public_pin
    assert sha(smoke / 'command_ir_dataflow_client.mm') == sha(client / 'command_ir_dataflow_client.mm')
    pv = numeric(smoke)
    return {'status': 'PASS', 'static_library_SHA256': pin, 'source_manifest_SHA256': sha(lib / 'manifest.json'),
            'client_SHA256': sha(client / 'command_ir_dataflow_client.mm'), 'GPU_cohorts': len(cases),
            'GPU_trials': sum(x['trials'] for x in cases), 'exact_uint32_results': sum(x['exact_uint32_results'] for x in cases),
            'consumer_invocations': sum(x['consumer_invocations'] for x in cases), 'guard_bytes': sum(x['guard_bytes'] for x in cases),
            'cases': cases, 'native_function_factory_observations': 20,
            'CPU_library_contract_cases': 82, 'lifecycle_cases': 98, 'legacy_contract_cases': 93,
            'lifecycle_controls': lifecycle, 'M1_trials': 12, 'M1_identical_common_files': 156, 'M1_semantic_matches': matches,
            'system_files_unchanged': 83, 'OCLP_unchanged': True, 'failed_preflight_preserved': True,
            'failure_cause': 'Negative native-compiler control ran after automatic producer-library activation; moved before activation',
            'runtime_modified_to_resolve_preflight': False, 'manual_function_registration_calls': 0, 'manual_encoder_adaptation_calls': 0,
            'integration_level': 2, 'scope': 'One explicit registration, six pinned source functions/programs, one scope-owned queue',
            'arbitrary_libraries_supported': False, 'installed_driver_modified': False, 'performance_benchmark': False,
            'public_source_rebuild': {'static_library_SHA256': public_pin, 'all_runtime_objects': 7, 'CPU_link_check': 'PASS',
                                     'GPU_smoke': {k: pv[k] for k in ['status', 'trials', 'exact_uint32_results', 'consumer_invocations', 'guard_bytes']},
                                     'full_296_trial_suite': 'NOT RUN; qualification is artifact-specific'},
            'full_objective_complete': False, 'Qwen_job_ids': []}

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--out', type=Path, required=True); a = p.parse_args()
    result = verify(); out = a.out.resolve(); out.relative_to(ROOT / 'results')
    with out.open('x') as f: json.dump(result, f, indent=2); f.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ['cases', 'M1_semantic_matches']}, indent=2))
