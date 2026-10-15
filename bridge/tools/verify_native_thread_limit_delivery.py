#!/usr/bin/env python3
"""Offline audit of native thread-limit observations and the bounded repair."""
from pathlib import Path
import argparse, hashlib, json
from verify_command_ir_dataflow import verify as numeric

ROOT = Path(__file__).resolve().parents[1]
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()

def verify():
    progress = ROOT / 'results/thread-limit-progress-20261015'
    lib = ROOT / 'results/thread-limit-runtime-library-build-20261015'
    lm = json.loads((lib / 'manifest.json').read_text())
    pin = sha(lib / 'libKeplerMetal.a')
    assert pin == lm['static_library_SHA256']
    for name, h in lm['source_SHA256'].items():
        assert sha(lib / name) == sha(ROOT / name) == h
    cpu = ROOT / 'results/thread-limit-contract-probe-20261015'
    d = json.loads((cpu / 'results.json').read_text())
    cm = json.loads((cpu / 'execution/manifest.json').read_text())
    assert cm['exit_code'] == 0 and not cm['SIGKILL_requested'] and not cm['authoritative_ps_status']
    assert len(d['runs']) == 70 and all(x['PASS'] for x in d['runs'])
    assert d['scope_released_with_reflection_alive'] and not d['command_buffers_submitted']
    assert sum(x['kind'] == 'thread_limit_encoding' and x['expected_refusal'] for x in d['runs']) == 12
    pending = ROOT / 'results/thread-limit-pending-probe-20261015'
    pd = json.loads((pending / 'results.json').read_text())
    pm = json.loads((pending / 'execution/manifest.json').read_text())
    assert pm['exit_code'] == 0 and not pm['SIGKILL_requested'] and not pm['authoritative_ps_status']
    assert len(pd['runs']) == 42 and all(x['PASS'] for x in pd['runs']) and pd['scope_released_with_reflection_alive']
    observations = json.loads((progress / 'native-observations-verification.json').read_text())
    for name, h in observations['raw_inputs_SHA256'].items():
        assert sha(name) == h
    cases = []
    for folder, key in [('thread-limit-factory-qualification-20261015', 'factory_kind'),
                        ('thread-limit-geometry-qualification-20261015', 'limit')]:
        suite = ROOT / 'results' / folder
        assert json.loads((suite / 'status.json').read_text())['status'] == 'PASS'
        for record in json.loads((suite / 'history.json').read_text()):
            assert record['exit_code'] == 0
            if record['phase'] != 'CPU':
                continue
            root = Path(record['result'])
            v = numeric(root)
            inp = json.loads((root / 'inputs.json').read_text())
            data = json.loads((root / 'results.json').read_text())
            assert inp['static_library_SHA256'] == pin
            e = data['factory_evidence']
            expected = (32 if data['factory_kind'] in [2, 5] else 0) if key == 'factory_kind' else (0 if record['limit'] == 'auto' else int(record['limit']))
            assert e['requested_max_threads'] == expected and e['max_threads'] == (expected or 1024)
            if expected:
                proof = data['producer_import']['native_thread_limit']
                assert proof['requested'] == proof['native_after'] == expected and proof['native_before'] == 1024
                assert proof['native_getter_unchanged'] and not proof['shader_optimizer_changed']
            if key == 'limit':
                threads = 32 if record['limit'] == 'auto' else int(record['limit'])
                if 'producer_local_threads' in inp:
                    assert inp['producer_local_threads'] == threads
                else:
                    # Earlier auto-control fixture: derive only from the exact
                    # frozen, hash-checked 32-thread client, never an assumed default.
                    assert record['limit'] == 'auto' and threads == 32
                    assert sha(root / 'command_ir_dataflow_client.mm') == sha(ROOT / 'results/thread-limit-32-client-build-20261015/command_ir_dataflow_client.mm')
                source = (root / 'command_ir_dataflow_client.mm').read_text()
                assert ('[e useResource:r usage:MTLResourceUsageRead|MTLResourceUsageWrite];[e dispatchThreadgroups:MTLSizeMake(1,1,1)threadsPerThreadgroup:MTLSizeMake(' + str(threads) + ',1,1)];') in source
            cases.append({'suite': key, 'case': record[key], 'mode': record['mode'],
                          **{k: v[k] for k in ['trials', 'exact_uint32_results', 'consumer_invocations', 'guard_bytes']}})
    comparison = json.loads((progress / 'M1-comparison.json').read_text())
    reference = ROOT / 'results/thread-limit-M1-dataflow-return-20261015/Reference'
    client = ROOT / 'results/thread-limit-32-client-build-20261015'
    assert sha(reference / 'command_ir_dataflow_client.mm') == sha(client / 'command_ir_dataflow_client.mm') == comparison['identical_client_SHA256']
    assert sha(reference / 'PipelineFactoryReception.inc') == sha(client / 'PipelineFactoryReception.inc')
    for mode in ['no_producer', 'barrier', 'no_consumer']:
        assert numeric(reference / 'results' / mode)['status'] == 'PASS'
    assert len(comparison['matches']) == 156
    for row in comparison['matches']:
        assert sha(reference / 'results' / row['mode'] / 'outputs' / row['file']) == row['SHA256']
        assert sha(ROOT / 'results' / ('thread-limit-final-20261015-k5-' + row['mode']) / 'outputs' / row['file']) == row['SHA256']
    previous = json.loads((ROOT / 'results/pipeline-contract-runtime-progress-20261015/final-verification.json').read_text())
    assert len(previous['system_files']) == 83
    assert all(sha(r['path']) == r['baseline_SHA256'] for r in previous['system_files'])
    assert sha('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist') == previous['OCLP_SHA256']
    return {'status': 'PASS', 'static_library_SHA256': pin,
            'source_manifest_SHA256': sha(lib / 'manifest.json'), 'GPU_cohorts': len(cases),
            'GPU_trials': sum(x['trials'] for x in cases),
            'exact_uint32_results': sum(x['exact_uint32_results'] for x in cases),
            'consumer_invocations': sum(x['consumer_invocations'] for x in cases),
            'guard_bytes': sum(x['guard_bytes'] for x in cases), 'cases': cases,
            'CPU_contract_cases': 70, 'CPU_pending_scope_cases': 42,
            'pre_encode_refusals': 12, 'native_pipeline_limits': [32,64,128,256,512,1024],
            'M1_trials': 12, 'M1_identical_common_files': 156,
            'M1_same_client_SHA256': comparison['identical_client_SHA256'],
            'system_files_unchanged': 83, 'OCLP_unchanged': True,
            'native_getter_replaced': False, 'shader_optimizer_changed': False,
            'integration_level': 2, 'enforcement_scope': 'Explicitly adapted compute encoders only',
            'unadapted_encoder_limit_enforcement': 'NOT IMPLEMENTED by this repair',
            'all_lanes_witnessed_in_producer': False,
            'producer_source_note': 'Only grid index0 generates commands; others return. Geometry tests validate requested group sizes and resulting command dataflow, not an independent invocation witness for every lane.',
            'performance_benchmark': False, 'full_objective_complete': False}

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    result = verify()
    out = a.out.resolve()
    out.relative_to(ROOT / 'results')
    with out.open('x') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k != 'cases'}, indent=2))
