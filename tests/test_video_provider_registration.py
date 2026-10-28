# SPDX-License-Identifier: MIT
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('registration', ROOT / 'bridge/experiments/video_provider_registration/inspect.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class RegistrationTests(unittest.TestCase):
    def test_sparse_mask_requires_all_intervening_words(self):
        self.assertEqual(m.assess(0, 0x80000001, [1])['reason'], 'short-table')
        self.assertEqual(m.assess(31, 0x80000000, [0] * 31 + [1])['required_words'], 32)
        self.assertTrue(m.assess(31, 0x80000000, [0] * 31 + [1])['eligible'])

    def test_each_bit_and_index_boundary(self):
        for i in range(32):
            words = [0] * (i + 1)
            words[i] = 7
            with self.subTest(i=i):
                self.assertTrue(m.assess(i, 1 << i, words)['eligible'])
                self.assertEqual(m.assess(i + 1, 1 << i, words)['reason'], 'index-out-of-range')
                self.assertEqual(m.assess(i, 1 << i, words[:-1])['reason'], 'short-table')
                words[i] = 0
                self.assertEqual(m.assess(i, 1 << i, words)['reason'], 'zero-entry')
        self.assertEqual(m.assess(1, 5, [1, 1, 1])['reason'], 'index-disabled')
        self.assertEqual(m.assess(0, 0, [])['reason'], 'zero-mask')

    def test_invalid_inputs_refused(self):
        for args in [(-1, 1, [1]), (0, 1 << 32, [1]), (True, 1, [1]), (0, 1, [-1]), (0, 1, b'1')]:
            with self.subTest(args=args), self.assertRaises(ValueError):
                m.assess(*args)

    def test_provider_mutation_refused(self):
        with self.assertRaisesRegex(ValueError, 'identity'):
            m.verify_provider(b'\xcf\xfa\xed\xfe' + b'\x00' * 32)


if __name__ == '__main__':
    unittest.main()
