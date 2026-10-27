# SPDX-License-Identifier: MIT
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge/tools'))
from verify_partial_dual_chain import expected
from verify_partial_general_api import expected_outputs

class DualChainOracleTests(unittest.TestCase):
    def test_3d_producer_matches_independent_oracle(self):
        coordinates, geometry, counter, count = expected_outputs(0, True)
        dual = expected(1, True, 3)
        # The existing oracle reserves 1024 elements; this test has exactly 385.
        end = 64 + count * 16
        self.assertEqual(dual['b'][:end], coordinates[:end])
        self.assertEqual(dual['geo'][:end], geometry[:end])
        self.assertEqual(dual['count1'], counter)

    def test_order_and_guards(self):
        for scenario in range(4):
            forward = expected(1, True, scenario)
            missing = expected(4, True, scenario)
            reverse = expected(5, True, scenario)
            self.assertNotEqual(forward['c'], missing['c'])
            self.assertEqual(missing['c'], reverse['c'])
            for row in (forward, missing, reverse):
                for value in row.values():
                    self.assertEqual(value[:64], b'\xa5' * 64)
                    self.assertEqual(value[-64:], b'\xa5' * 64)

if __name__ == '__main__':
    unittest.main()
