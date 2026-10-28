#!/usr/bin/env python3
"""Inspect explicit pointer uses in retained AIR; never authorize a repair."""
import argparse
import hashlib
import json
from pathlib import Path
from inspect_air_cfg import require
from trace_air_output import trace


def inspect(detail, cfg, old, name):
    projection = json.loads(json.dumps(detail))
    for fn in projection['functions']:
        for ins in fn['instructions']:
            for key in ('sub', 'flags', 'align'):
                require(key in ins, 'missing detailed instruction field')
                del ins[key]
    require(projection == cfg, 'CFG projection differs')
    output = trace(cfg, old, name)
    fn = detail['functions'][0]; instructions = fn['instructions']; values = fn['values']; types = detail['types']
    call = next(x for x in instructions if x.get('callee', '').startswith('air.atomic.local.cmpxchg.weak.i32'))
    pointer = call['operands'][2]; require(0 <= pointer < len(values), 'invalid pointer')
    definitions = [x for x in instructions if x['value'] == pointer]
    require(len(definitions) == 1 and definitions[0]['op'] == 13 and definitions[0]['block'] == 0,
            'entry alloca required')
    alloca = definitions[0]; typ = types[values[pointer]['type']]
    require(values[pointer]['kind'] == 10 and alloca['type'] == values[pointer]['type'] and
            typ['kind'] == 3 and typ['address_space'] == 0 and
            types[typ['element']]['kind'] == 2 and types[typ['element']]['bits'] == 32,
            'expected private i32 pointer')
    require(len(alloca['operands']) == 1, 'unknown allocation count')
    count = values[alloca['operands'][0]]
    require(count['kind'] == 2 and count['integer'] == 1, 'not one allocated element')
    uses = [x for x in instructions if pointer in x['operands']]
    casts = [x for x in uses if x['op'] == 1 and x['operands'] == [pointer]]
    require(len(casts) == 1 and casts[0]['sub'] == 11, 'one bitcast required')
    cast = casts[0]; alias = cast['value']
    require(alias != pointer and 0 <= alias < len(values), 'invalid cast result')
    alias_type = types[values[alias]['type']]
    require(values[alias]['kind'] == 10 and cast['type'] == values[alias]['type'] and
            alias_type['kind'] == 3 and alias_type['address_space'] == 0 and
            types[alias_type['element']]['kind'] == 2 and types[alias_type['element']]['bits'] == 8,
            'bitcast must produce a private i8 pointer')
    alias_uses = [x for x in instructions if alias in x['operands']]
    start = [x for x in alias_uses if x.get('callee') == 'llvm.lifetime.start.p0i8']
    end = [x for x in alias_uses if x.get('callee') == 'llvm.lifetime.end.p0i8']
    require(len(alias_uses) == 2 and len(start) == len(end) == 1, 'unexpected cast-pointer use')
    for marker in (start[0], end[0]):
        require(marker['op'] == 16 and len(marker['operands']) == 3 and marker['operands'][2] == alias,
                'unsupported lifetime marker')
        size = values[marker['operands'][1]]
        require(size['kind'] == 2 and size['integer'] == 4, 'unexpected lifetime size')
    stores = [x for x in uses if x['op'] == 15 and len(x['operands']) == 2 and x['operands'][0] == pointer]
    loads = [x for x in uses if x['op'] == 14 and x['operands'] == [pointer]]
    require(len(stores) == len(loads) == 1 and len(uses) == 4 and call in uses,
            'unexpected direct pointer use')
    require(call['operands'].count(pointer) == 1 and stores[0]['operands'].count(pointer) == 1,
            'pointer appears in another operand')
    group = [cast, start[0], stores[0], call, loads[0], end[0]]
    require(all(x['block'] == call['block'] for x in group) and
            [x['index'] for x in group] == sorted(x['index'] for x in group) and
            len({x['index'] for x in group}) == len(group), 'pointer use order differs')
    require(stores[0]['index'] < call['index'] < loads[0]['index'], 'CAS order differs')
    return {'status': 'OBSERVED', 'alloca_instruction': alloca['index'],
            'cast_instruction': cast['index'], 'cast_subcode': cast['sub'],
            'lifetime_start_instruction': start[0]['index'], 'initial_store_instruction': stores[0]['index'],
            'CAS_instruction': call['index'], 'expected_load_instruction': loads[0]['index'],
            'lifetime_end_instruction': end[0]['index'], 'direct_pointer_uses': len(uses),
            'cast_pointer_uses': len(alias_uses), 'output_component': output['component'],
            'authorizes_repair': False,
            'limits': 'Explicit reader-derived operands only; no independent AIR decoder, indirect/hidden aliases, SASS flow or new GPU test.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('detail', 'cfg', 'previous', 'out'):
        p.add_argument('--' + key, type=Path, required=True)
    p.add_argument('--function', required=True); a = p.parse_args()
    raw = [x.read_bytes() for x in (a.detail, a.cfg, a.previous)]
    result = inspect(*(json.loads(x) for x in raw), a.function)
    result['inputs_sha256'] = [hashlib.sha256(x).hexdigest() for x in raw]
    with a.out.open('x') as f:
        json.dump(result, f, indent=2, sort_keys=True); f.write('\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
