#!/usr/bin/env python3
"""Offline CFG evidence for a conditional CAS; never authorizes a repair."""
import argparse
import hashlib
import json
from pathlib import Path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def inspect(module, old, name):
    # The additional block IDs must come from the same AIR and add no changes
    # to the original typed representation. This is not independent validation
    # of the underlying AIR reader.
    projection = json.loads(json.dumps(module))
    for function in projection['functions']:
        for ins in function['instructions']:
            require('blocks' in ins, 'missing block IDs')
            del ins['blocks']
    require(projection == old, 'previous typed AIR differs')
    require(len(module['functions']) == 1 and module['functions'][0]['name'] == name,
            'unexpected function')
    fn = module['functions'][0]
    count = fn['blocks']
    require(isinstance(count, int) and 1 <= count <= 1024, 'invalid block count')
    instructions = fn['instructions']
    grouped = [[] for _ in range(count)]
    for index, ins in enumerate(instructions):
        require(ins['index'] == index and isinstance(ins['block'], int) and 0 <= ins['block'] < count,
                'invalid instruction index or block')
        grouped[ins['block']].append(ins)
    edges = []
    for block, group in enumerate(grouped):
        require(group and group[-1]['op'] in (8, 9, 10, 11), 'missing terminator')
        require(all(x['op'] not in (8, 9, 10, 11) for x in group[:-1]), 'early terminator')
        end = group[-1]
        targets = end['blocks']
        require(all(isinstance(x, int) and 0 <= x < count for x in targets), 'invalid target')
        if end['op'] == 9:
            require((len(targets), len(end['operands'])) in ((1, 0), (2, 1)), 'invalid branch')
        elif end['op'] == 10:
            require(len(targets) == len(end['operands']) and len(targets) >= 1, 'invalid switch')
        else:
            require(not targets, 'unexpected return target')
        edges.extend((block, target) for target in targets)
    predecessors = [set() for _ in range(count)]
    for source, target in edges:
        predecessors[target].add(source)
    reachable = {0}
    while True:
        next_reachable = reachable | {target for source, target in edges if source in reachable}
        if next_reachable == reachable:
            break
        reachable = next_reachable
    require(len(reachable) == count, 'unreachable blocks require separate analysis')
    for block, group in enumerate(grouped):
        for ins in group:
            if ins['op'] == 12:
                require(len(ins['blocks']) == len(ins['operands']) and
                        len(set(ins['blocks'])) == len(ins['blocks']) and
                        set(ins['blocks']) == predecessors[block], 'phi predecessors differ')
    calls = [i for i in instructions if i.get('callee', '').startswith('air.atomic.local.cmpxchg.weak.i32')]
    require(len(calls) == 1 and len(calls[0]['operands']) >= 3, 'unique CAS required')
    call = calls[0]; pointer = call['operands'][2]; block = call['block']
    loads = [x for x in grouped[block] if x['op'] == 14 and x['operands'] == [pointer]
             and x['index'] > call['index']]
    require(len(loads) == 1, 'unique local expected load required')
    load = loads[0]
    require(all(x['op'] not in (9, 10, 12, 15, 16) for x in instructions[call['index'] + 1:load['index']]),
            'intervening control or memory operation')
    stores = [x for x in grouped[block] if x['op'] == 15 and x['operands'][0] == pointer
              and x['index'] < call['index']]
    require(len(stores) == 1, 'unique initialization required')
    initial = stores[0]['operands'][1]
    phi = [x for x in instructions if x['op'] == 12 and load['value'] in x['operands']]
    require(len(phi) == 1 and len(phi[0]['operands']) == 2, 'unique two-input phi required')
    phi = phi[0]; incoming = dict(zip(phi['blocks'], phi['operands']))
    require(incoming.get(block) == load['value'] and len(predecessors[phi['block']]) == 2,
            'load is not an incoming CAS-block value')
    other = next(x for x in incoming if x != block)
    require(incoming[other] == initial, 'fallback differs from initialized expected value')
    require(grouped[block][-1]['op'] == 9 and grouped[block][-1]['blocks'] == [phi['block']],
            'CAS block must branch directly to phi')
    insert = [x for x in instructions if x['op'] == 5 and x['operands'][1] == phi['value']]
    require(len(insert) == 1, 'unique vector insertion required')
    item = insert[0]; index = fn['values'][item['operands'][2]]
    require(index['integer'] in range(4) and
            (index['kind'] == 2 or (index['kind'] == 4 and index['integer'] == 0)),
            'invalid insertion component')
    return {'status': 'OBSERVED', 'blocks': count, 'edges': len(edges),
            'CAS_instruction': call['index'], 'expected_load_instruction': load['index'],
            'initial_store_instruction': stores[0]['index'], 'phi_instruction': phi['index'],
            'phi_block': phi['block'], 'CAS_block': block, 'fallback_block': other,
            'vector_insertion_instruction': item['index'], 'inserted_component': index['integer'],
            'authorizes_repair': False,
            'limits': 'Reader-derived structural observation only; no alias, dominance, full output, native SASS or GPU qualification.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ('cfg', 'previous', 'out'):
        parser.add_argument('--' + option, type=Path, required=True)
    parser.add_argument('--function', required=True)
    args = parser.parse_args()
    raw = args.cfg.read_bytes(); prior = args.previous.read_bytes()
    result = inspect(json.loads(raw), json.loads(prior), args.function)
    result['cfg_SHA256'] = hashlib.sha256(raw).hexdigest()
    result['previous_SHA256'] = hashlib.sha256(prior).hexdigest()
    with args.out.open('x') as out:
        json.dump(result, out, indent=2, sort_keys=True); out.write('\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
