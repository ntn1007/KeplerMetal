#!/usr/bin/env python3
"""Freeze decoded conversion programs and raw inputs; never import or dispatch."""
from pathlib import Path
import argparse, hashlib, json
from fp64_conversion_inputs import OPS, columns, packed

ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser()
p.add_argument('--compiled', type=Path, required=True)
p.add_argument('--out', type=Path, required=True)
a = p.parse_args()
compiled, out = a.compiled.resolve(), a.out.resolve()
compiled.relative_to(ROOT / 'results'); out.relative_to(ROOT / 'results')
assert not out.exists(); out.mkdir()
sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
summary = json.loads((compiled / 'summary.json').read_text())
assert len(summary['records']) == 9 and not summary['GPU_execution']
assert {(r['operation'], r['local']) for r in summary['records']} == {(op, local) for op in OPS for local in (32, 128, 1024)}
carrier = out / 'kepler_carrier.metallib'
carrier.write_bytes((ROOT / 'build/kepler_carrier.metallib').read_bytes())
plans = []
for row in summary['records']:
    op, local = row['operation'], row['local']
    assert row['compiled'] and row['known_decode'] and not row['info']['strided_inputs']
    label = f'{op}-l{local}'
    decoded = (compiled / (label + '-decode.stdout')).read_text()
    instruction = {'from_i64':'cvt rn f64', 'from_u64':'cvt rn f64', 'from_f32':'cvt f64'}[op]
    conversions = [line for line in decoded.splitlines() if instruction in line]
    assert conversions and ({'from_i64':'s64', 'from_u64':'u64', 'from_f32':'f32'}[op] in conversions[0])
    code = out / (label + '.sass'); code.write_bytes((compiled / (label + '.sass')).read_bytes())
    assert sha(code) == row['code_SHA256']
    count = {32:33, 128:1041, 1024:8193}[local]
    fixtures = []
    for trial in range(3):
        fixture = {'trial':trial, 'count':count, 'nonce':0x91c40017 ^ (local * 37 + trial * 101)}
        for name, values in zip(('A','B','C'), columns(op, local, count, trial)):
            path = out / f'{label}-t{trial}-{name}.bin'; path.write_bytes(packed(values))
            fixture[name], fixture[name+'_SHA256'] = str(path), sha(path)
        fixtures.append(fixture)
    plan = {'shader_info':row['info'], 'code':str(code), 'code_SHA256':sha(code), 'carrier':str(carrier), 'carrier_SHA256':sha(carrier), 'fixtures':fixtures, 'recipe':'fp64-conversions-v1', 'conversion_instructions':conversions}
    path = out / (label + '.plan.json'); path.write_text(json.dumps(plan, indent=2)+'\n'); plans.append(str(path))
(out / 'summary.json').write_text(json.dumps({'plans':plans, 'GPU_execution':False, 'compiler':summary, 'input_recipe_SHA256':sha(ROOT/'tools/fp64_conversion_inputs.py')}, indent=2)+'\n')
print(json.dumps({'plans':len(plans), 'GPU_execution':False}))
