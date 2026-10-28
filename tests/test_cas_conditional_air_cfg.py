"""Synthetic control-flow safety checks; no shader is dispatched."""
import copy
import importlib.util
import unittest
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / 'bridge/experiments/cas_divergence/inspect_air_cfg.py'
spec = importlib.util.spec_from_file_location('inspect_air_cfg', PATH)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


def example():
    records = [
        (0, 9, 0, [4], [1, 2]),
        (1, 15, 1, [10, 11], []),
        (2, 16, 1, [1, 2, 10], []),
        (3, 14, 1, [10], []),
        (4, 9, 1, [], [2]),
        (5, 12, 2, [13, 11], [1, 0]),
        (6, 5, 2, [20, 15, 0], []),
        (7, 8, 2, [], []),
    ]
    ins = []
    for index, op, block, operands, blocks in records:
        item = {'index': index, 'op': op, 'block': block, 'operands': operands,
                'blocks': blocks, 'value': {3: 13, 5: 15}.get(index, 0xffffffff)}
        if index == 2:
            item['callee'] = 'air.atomic.local.cmpxchg.weak.i32'
        ins.append(item)
    return {'functions': [{'name': 'test', 'blocks': 3,
                           'values': [{'kind': 4, 'integer': 0}], 'instructions': ins}]}


def projected(module):
    result = copy.deepcopy(module)
    for ins in result['functions'][0]['instructions']:
        del ins['blocks']
    return result


class ConditionalCFG(unittest.TestCase):
    def test_valid_shape_is_observation_only(self):
        m = example(); result = tool.inspect(m, projected(m), 'test')
        self.assertEqual(result['inserted_component'], 0)
        self.assertEqual(result['phi_instruction'], 5)
        self.assertFalse(result['authorizes_repair'])

    def test_changed_old_evidence_is_refused(self):
        m = example(); old = projected(m); old['functions'][0]['instructions'][3]['operands'] = [99]
        with self.assertRaisesRegex(ValueError, 'previous typed AIR differs'):
            tool.inspect(m, old, 'test')

    def test_wrong_phi_edges_or_value_are_refused(self):
        for mutation in ('missing-predecessor', 'swap-values', 'wrong-fallback'):
            m = example(); phi = m['functions'][0]['instructions'][5]
            if mutation == 'missing-predecessor': phi['blocks'] = [1, 1]
            if mutation == 'swap-values': phi['operands'] = [11, 13]
            if mutation == 'wrong-fallback': phi['operands'] = [13, 22]
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                tool.inspect(m, projected(m), 'test')

    def test_bad_edges_and_early_terminator_are_refused(self):
        for mutation in ('bad-target', 'no-cas-edge', 'early-terminator'):
            m = example(); ins = m['functions'][0]['instructions']
            if mutation == 'bad-target': ins[0]['blocks'] = [1, 99]
            if mutation == 'no-cas-edge': ins[4]['blocks'] = [1]
            if mutation == 'early-terminator': ins[1]['op'] = 9
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                tool.inspect(m, projected(m), 'test')

    def test_missing_block_metadata_is_refused(self):
        m = example(); old = projected(m); del m['functions'][0]['instructions'][0]['blocks']
        with self.assertRaisesRegex(ValueError, 'missing block IDs'):
            tool.inspect(m, old, 'test')

    def test_nonzero_null_index_is_refused(self):
        m = example(); m['functions'][0]['values'][0]['integer'] = 2
        with self.assertRaisesRegex(ValueError, 'invalid insertion component'):
            tool.inspect(m, projected(m), 'test')


if __name__ == '__main__':
    unittest.main()
