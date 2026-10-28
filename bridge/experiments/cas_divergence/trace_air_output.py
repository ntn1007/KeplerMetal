#!/usr/bin/env python3
"""Trace one retained conditional-CAS value to a device store, offline only."""
import argparse
import hashlib
import json
from pathlib import Path
from inspect_air_cfg import inspect, require


def trace(module, old, name):
    observation = inspect(module, old, name)
    fn = module['functions'][0]; ins = fn['instructions']; values = fn['values']; types = module['types']
    count = fn['blocks']; groups = [[] for _ in range(count)]
    for item in ins:
        groups[item['block']].append(item)
    predecessors = [set() for _ in range(count)]
    for block, group in enumerate(groups):
        for target in group[-1]['blocks']:
            predecessors[target].add(block)
    dominators = [{0} if b == 0 else set(range(count)) for b in range(count)]
    while True:
        changed = False
        for b in range(1, count):
            require(predecessors[b], 'block without predecessor')
            new = {b} | set.intersection(*(dominators[p] for p in predecessors[b]))
            if new != dominators[b]:
                dominators[b] = new; changed = True
        if not changed:
            break
    definitions = {}
    for item in ins:
        value = item['value']
        if value != 0xffffffff:
            require(value not in definitions, 'duplicate SSA definition')
            definitions[value] = item

    def available(value, block, before):
        require(isinstance(value, int) and 0 <= value < len(values), 'value outside table')
        node = definitions.get(value)
        if node is None:
            # Instruction values must not masquerade as constants or arguments.
            require(values[value]['kind'] != 10, 'instruction value without definition')
            return
        require(values[value]['kind'] == 10, 'definition is not an instruction value')
        require(node['block'] in dominators[block] and
                (node['block'] != block or node['index'] < before), 'definition does not dominate use')

    init = ins[observation['initial_store_instruction']]
    phi = ins[observation['phi_instruction']]
    insertion = ins[observation['vector_insertion_instruction']]
    available(init['operands'][1], init['block'], init['index'])
    for block, value in zip(phi['blocks'], phi['operands']):
        available(value, block, groups[block][-1]['index'])
    available(phi['value'], insertion['block'], insertion['index'])

    component = observation['inserted_component']
    vector = types[insertion['type']]
    require(vector['kind'] == 4 and vector['count'] == 4 and
            types[vector['element']]['kind'] == 2 and types[vector['element']]['bits'] == 32,
            'insertion is not uint4-shaped')
    found = []
    for store in ins:
        if store['op'] != 15 or len(store['operands']) != 2:
            continue
        node_value = store['operands'][1]; path = []; seen = set(); target = None
        while node_value in definitions and node_value not in seen:
            seen.add(node_value); node = definitions[node_value]
            if node['value'] == insertion['value']:
                target = node; break
            if node['op'] != 5 or len(node['operands']) != 3:
                break
            require(node['type'] == insertion['type'], 'vector type changes along chain')
            idx = values[node['operands'][2]]
            require(idx['kind'] == 2 or (idx['kind'] == 4 and idx['integer'] == 0),
                    'dynamic insertion index')
            require(0 <= idx['integer'] < 4, 'invalid insertion index')
            require(idx['integer'] != component, 'expected component overwritten')
            path.append(node)
            node_value = node['operands'][0]
        if target is None:
            continue
        # SSA chain must be valid at each use, including same-block ordering.
        previous = target
        for later in reversed(path):
            available(previous['value'], later['block'], later['index']); previous = later
        available(previous['value'], store['block'], store['index'])
        pointer = values[store['operands'][0]]; pointer_type = types[pointer['type']]
        require(pointer_type['kind'] == 3 and pointer_type['address_space'] == 1 and
                pointer_type['element'] == insertion['type'], 'store is not a device uint4 store')
        available(store['operands'][0], store['block'], store['index'])
        found.append((store, [target['index']] + [x['index'] for x in reversed(path)]))
    require(len(found) == 1, 'unique preserving device store required')
    store, path = found[0]
    return {'status': 'OBSERVED', 'phi_instruction': phi['index'], 'phi_block': phi['block'],
            'insertion_chain': path, 'device_store_instruction': store['index'],
            'device_store_block': store['block'], 'component': component,
            'phi_dominates_store_block': phi['block'] in dominators[store['block']],
            'all_paths_reach_store_proved': False, 'authorizes_repair': False,
            'limits': 'Reader-derived SSA/CFG observation; no independent AIR decoding, memory alias proof, SASS flow or GPU qualification.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('cfg', 'previous', 'out'):
        p.add_argument('--' + key, type=Path, required=True)
    p.add_argument('--function', required=True); a = p.parse_args()
    cfg = a.cfg.read_bytes(); old = a.previous.read_bytes()
    result = trace(json.loads(cfg), json.loads(old), a.function)
    result['cfg_sha256'] = hashlib.sha256(cfg).hexdigest()
    result['previous_sha256'] = hashlib.sha256(old).hexdigest()
    with a.out.open('x') as f:
        json.dump(result, f, indent=2, sort_keys=True); f.write('\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
