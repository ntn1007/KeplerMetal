#!/usr/bin/env python3
"""Compare offline AIR path verdicts using mutated parsed JSON, not GPU code."""
import argparse
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys


def need(value, why):
    if not value:
        raise ValueError(why)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--previous', required=True, type=Path)
parser.add_argument('--cases', required=True, type=Path)
parser.add_argument('--out', required=True, type=Path)
a = parser.parse_args()
need(not a.out.exists() and a.out.parent.is_dir(), 'fresh output required')
current_path = Path(__file__).resolve().parent / 'recognize_native_cas.py'
old, new = load(a.previous, 'previous_cas_path'), load(current_path, 'current_cas_path')
rows = []
for name in ('slot1', 'live_noise', 'permuted', 'original_compare_control'):
    path = a.cases / name / 'typed-air.json'
    source = json.loads(path.read_bytes())
    before, after = old.air_contract(source), new.air_contract(source)
    expected = name != 'original_compare_control'
    need(before['qualified'] == after['qualified'] == expected, 'baseline changed: ' + name)
    rows.append({'case': name, 'typed_air_sha256': sha(path),
                 'kind': 'retained_parsed_air', 'before': before['qualified'],
                 'after': after['qualified'], 'component': after.get('expected_output_component')})
    if not expected:
        continue
    for mode in ('insert_other_block', 'store_other_block'):
        mutated = copy.deepcopy(source)
        ins = mutated['functions'][0]['instructions']
        load_instruction = next(x for x in ins if x['index'] == before['expected_load_instruction'])
        insert = next(x for x in ins if x['op'] == 5 and x['operands'][1] == load_instruction['value'])
        store = next(x for x in ins if x['index'] == before['output_store_instruction'])
        (insert if mode == 'insert_other_block' else store)['block'] += 100
        before_mutated, after_mutated = old.air_contract(mutated), new.air_contract(mutated)
        need(before_mutated['qualified'] and not after_mutated['qualified'], 'mutation verdict: ' + name + '/' + mode)
        rows.append({'case': name, 'kind': mode, 'before': True, 'after': False,
                     'reason': after_mutated['reason']})

result = {'status': 'PASS', 'previous_source_sha256': sha(a.previous),
          'current_source_sha256': sha(current_path), 'rows': rows,
          'mutations_are_parsed_json_only': True, 'compiled_mutated_air': False,
          'gpu_execution': False, 'prior_certificates_changed': False}
with a.out.open('x') as stream:
    json.dump(result, stream, indent=2, sort_keys=True)
    stream.write('\n')
print(json.dumps({'status': result['status'], 'cases': len(rows)}))
