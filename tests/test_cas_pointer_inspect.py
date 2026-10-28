"""Synthetic explicit pointer-use counterexamples; no GPU execution."""
import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bridge/experiments/cas_divergence'))
sys.path.insert(0, str(ROOT / 'tests'))
from inspect_cas_pointer import inspect
from test_cas_air_output_trace import fixture as base
from test_cas_conditional_air_cfg import projected


def fixture():
    m = base(); fn = m['functions'][0]; original = fn['instructions']
    m['types'] += [{'kind': 3, 'address_space': 0, 'element': 0},
                   {'kind': 2, 'bits': 8}, {'kind': 3, 'address_space': 0, 'element': 4}]
    values = fn['values']; values.extend({'kind': 2, 'integer': 0, 'type': 0} for _ in range(3))
    values[10] = {'kind': 10, 'integer': 0, 'type': 3}
    values[22] = {'kind': 2, 'integer': 4, 'type': 0}
    values[23] = {'kind': 10, 'integer': 0, 'type': 5}
    values[24] = {'kind': 2, 'integer': 1, 'type': 0}
    def node(op, block, operands, value=0xffffffff, typ=0xffffffff, callee=None):
        x = {'op':op, 'block':block, 'operands':operands, 'value':value,
             'type':typ, 'blocks':[], 'sub':0, 'flags':0, 'align':0}
        if callee: x['callee'] = callee
        return x
    alloc = node(13, 0, [24], 10, 3)
    cast = node(1, 1, [10], 23, 5); cast['sub'] = 11
    start = node(16, 1, [2, 22, 23], callee='llvm.lifetime.start.p0i8')
    end = node(16, 1, [3, 22, 23], callee='llvm.lifetime.end.p0i8')
    ins = [alloc, original[0], cast, start, original[1], original[2], original[3],
           end, original[4], original[5], original[6], original[7], original[8]]
    for i, item in enumerate(ins):
        item['index'] = i
        for key in ('sub', 'flags', 'align'): item.setdefault(key, 0)
    fn['instructions'] = ins
    return m


def inputs(m):
    cfg = copy.deepcopy(m)
    for ins in cfg['functions'][0]['instructions']:
        for key in ('sub', 'flags', 'align'): del ins[key]
    return cfg, projected(cfg)


def run(m):
    cfg, old = inputs(m)
    return inspect(m, cfg, old, 'test')


class PointerInspection(unittest.TestCase):
    def test_explicit_uses_and_lifetimes(self):
        result = run(fixture())
        self.assertEqual((result['direct_pointer_uses'], result['cast_pointer_uses']), (4, 2))
        self.assertFalse(result['authorizes_repair'])

    def test_escape_via_cast_pointer_is_rejected(self):
        m = fixture(); m['functions'][0]['instructions'][7]['callee'] = 'unknown.function'
        with self.assertRaisesRegex(ValueError, 'unexpected cast-pointer use'): run(m)

    def test_extra_direct_use_is_rejected(self):
        m = fixture(); ins = m['functions'][0]['instructions']
        extra = {'op': 16, 'block': 1, 'operands': [4, 10], 'value': 0xffffffff,
                 'type': 0xffffffff, 'blocks': [], 'sub': 0, 'flags': 0, 'align': 0,
                 'callee': 'unknown.function'}
        ins.insert(8, extra)
        for n, x in enumerate(ins): x['index'] = n
        with self.assertRaisesRegex(ValueError, 'unexpected direct pointer use'): run(m)

    def test_bad_cast_size_and_order_are_rejected(self):
        for case in ('cast', 'size', 'order', 'type'):
            m = fixture(); ins = m['functions'][0]['instructions']
            if case == 'cast': ins[2]['sub'] = 12
            if case == 'size': m['functions'][0]['values'][22]['integer'] = 8
            if case == 'order': ins[3], ins[7] = ins[7], ins[3]
            if case == 'type': m['types'][5]['address_space'] = 1
            for n, x in enumerate(ins): x['index'] = n
            with self.subTest(case=case), self.assertRaises(ValueError): run(m)

    def test_changed_detail_projection_rejected(self):
        m = fixture(); cfg, old = inputs(m)
        m['functions'][0]['instructions'][2]['operands'] = [11]
        with self.assertRaisesRegex(ValueError, 'CFG projection differs'): inspect(m, cfg, old, 'test')


if __name__ == '__main__': unittest.main()
