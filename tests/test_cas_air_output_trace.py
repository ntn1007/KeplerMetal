"""Synthetic SSA/output counterexamples; no synthetic GPU programs."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bridge/experiments/cas_divergence'))
sys.path.insert(0, str(ROOT / 'tests'))
from trace_air_output import trace
from test_cas_conditional_air_cfg import example, projected


def fixture():
    m = example(); fn = m['functions'][0]; ins = fn['instructions']
    m['types'] = [{'kind': 2, 'bits': 32}, {'kind': 4, 'count': 4, 'element': 0},
                  {'kind': 3, 'address_space': 1, 'element': 1}]
    fn['values'] = [{'kind': 2, 'integer': 0, 'type': 0} for _ in range(23)]
    fn['values'][0] = {'kind': 4, 'integer': 0, 'type': 0}
    fn['values'][1] = {'kind': 2, 'integer': 1, 'type': 0}
    fn['values'][11]['integer'] = 123
    for value in (13, 15, 16, 17): fn['values'][value]['kind'] = 10
    fn['values'][20] = {'kind': 5, 'integer': 0, 'type': 1}
    fn['values'][21] = {'kind': 9, 'integer': 0, 'type': 2}
    ins[6].update(value=16, type=1)
    ins[7] = {'index': 7, 'op': 15, 'block': 2, 'operands': [21, 16],
              'blocks': [], 'value': 0xffffffff}
    ins.append({'index': 8, 'op': 8, 'block': 2, 'operands': [],
                'blocks': [], 'value': 0xffffffff})
    return m


class OutputTrace(unittest.TestCase):
    def test_device_store_and_dominance(self):
        m = fixture(); result = trace(m, projected(m), 'test')
        self.assertEqual(result['insertion_chain'], [6])
        self.assertEqual(result['device_store_instruction'], 7)
        self.assertTrue(result['phi_dominates_store_block'])
        self.assertFalse(result['authorizes_repair'])

    def test_later_component_write_is_rejected(self):
        m = fixture(); ins = m['functions'][0]['instructions']
        ins[7:7] = [{'index': 7, 'op': 5, 'block': 2, 'operands': [16, 11, 0],
                     'blocks': [], 'type': 1, 'value': 17}]
        ins[8]['index'] = 8; ins[8]['operands'][1] = 17; ins[9]['index'] = 9
        with self.assertRaisesRegex(ValueError, 'component overwritten'):
            trace(m, projected(m), 'test')
        ins[7]['operands'][2] = 1
        self.assertEqual(trace(m, projected(m), 'test')['insertion_chain'], [6, 7])

    def test_non_device_store_is_rejected(self):
        m = fixture(); m['types'][2]['address_space'] = 3
        with self.assertRaisesRegex(ValueError, 'not a device'):
            trace(m, projected(m), 'test')

    def test_non_dominating_initial_value_is_rejected(self):
        m = fixture(); ins = m['functions'][0]['instructions']
        ins[1]['operands'][1] = 13
        ins[5]['operands'][1] = 13
        with self.assertRaises(ValueError):
            trace(m, projected(m), 'test')

    def test_missing_store_and_undefined_instruction_are_rejected(self):
        m = fixture(); m['functions'][0]['instructions'][7]['operands'][1] = 20
        with self.assertRaisesRegex(ValueError, 'unique preserving device store'):
            trace(m, projected(m), 'test')
        m = fixture(); m['functions'][0]['values'][11]['kind'] = 10
        with self.assertRaisesRegex(ValueError, 'without definition'):
            trace(m, projected(m), 'test')

    def test_store_reachable_without_phi_is_rejected(self):
        m = fixture(); fn = m['functions'][0]; ins = fn['instructions']
        fn['blocks'] = 4
        ins[0].update(op=10, operands=[4, 0, 1], blocks=[1, 2, 3])
        store = ins[7]; store['index'] = 8; store['block'] = 3
        ins[7] = {'index': 7, 'op': 9, 'block': 2, 'operands': [], 'blocks': [3],
                  'value': 0xffffffff}
        ins[8] = store
        ins.append({'index': 9, 'op': 8, 'block': 3, 'operands': [],
                    'blocks': [], 'value': 0xffffffff})
        with self.assertRaisesRegex(ValueError, 'does not dominate'):
            trace(m, projected(m), 'test')


if __name__ == '__main__':
    unittest.main()
