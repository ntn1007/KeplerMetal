#!/usr/bin/env python3
"""Verify raw conversion captures using integer bit construction on the CPU."""
from pathlib import Path
import argparse, hashlib, json, struct
from fp64_conversion_inputs import OPS, columns, packed, expected_bits, equivalent

sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()


def verify(root, portable=False, *, operators=OPS, recipe='fp64-conversions-v1', column_function=columns, result_function=expected_bits, compare_function=equivalent):
    root = Path(root)
    read = lambda name: json.loads((root/name).read_text())
    plan, result, manifest, inputs = [read(name) for name in ('plan.json','results.json','execution/manifest.json','inputs.json')]
    info = plan['shader_info']; op = info['operation']; mode = result['mode']
    assert op in operators and plan['recipe'] == recipe and plan['conversion_instructions']
    assert mode in ('prepare','execute','native') and result['operation'] == op and result['local'] == info['local']
    assert result['registry_id'] == 4294968458 and result['constructor_restored']
    assert not result['system_modified'] and not result['performance_benchmark'] and not result['CPU_computed_expected_outputs']
    assert manifest['exit_code'] == 0 and not manifest['SIGKILL_requested'] and not manifest['authoritative_ps_status'] and manifest['GPU_reservation']['state'] == 'terminal'
    for name, digest in inputs['source_SHA256'].items(): assert sha(root/name) == digest
    assert sha(root/'program.sass') == plan['code_SHA256'] and sha(root/'carrier.metallib') == plan['carrier_SHA256']
    if not portable:
        assert sha(root/'fp64_math_probe') == manifest['original_binary_sha256'] and sha(root/'execution/fp64_math_probe') == manifest['signed_binary_sha256']
    if mode != 'native':
        proof = result['import']
        assert proof['contract_verified'] and proof['target_imports'] == proof['verified_imports'] > 0 and not proof['rejected_import']
        for e in proof['events']:
            assert e['imported_code_identical'] and e['metadata_bytes_preserved_except_import_fields'] and e['code_input_unchanged_after_constructor']
            assert e['decoded_code_bytes'] == info['code_bytes'] and e['decoded_registers'] == info['registers']
    assert len(result['runs']) == len(plan['fixtures']) == 3
    mismatches = tag_errors = correct = tagged = guards = total = 0; errors = []; hashes = {}
    for f, r in zip(plan['fixtures'], result['runs']):
        n, trial, nonce = f['count'], f['trial'], f['nonce']
        assert n == {32:33,128:1041,1024:8193}[info['local']] and r['count'] == n and r['trial'] == trial and r['nonce'] == nonce
        assert r['committed'] == (mode != 'prepare') and r['command_status'] == (0 if mode == 'prepare' else 4) and r['upload_status'] == r['readback_status'] == 4
        values = column_function(op, info['local'], n, trial)
        for name, raw_values in zip(('A','B','C'), values):
            source = root/f'trial-{trial}-{name}.input.bin'
            assert source.read_bytes() == packed(raw_values) and sha(source) == f[name+'_SHA256']
            path = root/'outputs'/r['files'][name]; raw = path.read_bytes(); hashes[path.name] = sha(path)
            assert raw == b'\xa5'*64 + source.read_bytes() + b'\xa5'*64
            guards += 128
        path = root/'outputs'/r['files']['output']; raw = path.read_bytes(); hashes[path.name] = sha(path)
        assert len(raw) == (n+64)*16+128 and raw[:64] == b'\xa5'*64 and raw[64+n*16:] == b'\xa5'*1088, 'Guard violation: stop GPU tests'
        guards += 1152
        if mode == 'prepare':
            assert raw == b'\xa5'*len(raw); continue
        for i, source in enumerate(values[0]):
            observed, index, stamp = struct.unpack_from('<QII', raw, 64+i*16)
            wanted = result_function(op, source); good = compare_function(observed, wanted); tag = index == i and stamp == nonce
            correct += good; tagged += tag; mismatches += not good; tag_errors += not tag; total += 1
            if not good and len(errors)<24: errors.append({'trial':trial, 'index':i, 'raw_input':f'{source:016x}', 'observed':f'{observed:016x}', 'expected':f'{wanted:016x}'})
    status = 'PASS' if mismatches == tag_errors == 0 else 'FAIL'
    if mode == 'native':
        assert mismatches and tag_errors; status = 'PASS_EXPECTED_DIFFERENCE'
    return {'status':status, 'mode':mode, 'operation':op, 'local':info['local'], 'exact_results':correct, 'results_checked':total, 'numeric_mismatches':mismatches, 'tag_mismatches':tag_errors, 'GPU_invocations_with_correct_tags':tagged, 'guard_bytes_verified':guards, 'main_command_buffers':0 if mode=='prepare' else 3, 'conversion_instructions':plan['conversion_instructions'], 'oracle':'Integer-only bit construction and ties-to-even; quiet NaN classification', 'raw_SHA256':hashes, 'errors':errors, 'integration_level':1, 'performance_benchmark':False, 'general_IEEE_conformance':False}


if __name__ == '__main__':
    p=argparse.ArgumentParser(); p.add_argument('root',type=Path);p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args()
    v=verify(a.root.resolve(),a.portable)
    if a.out: a.out.write_text(json.dumps(v,indent=2)+'\n')
    print(json.dumps({k:x for k,x in v.items() if k not in ('raw_SHA256','errors')},indent=2))
    raise SystemExit(0 if v['status'].startswith('PASS') else 1)
