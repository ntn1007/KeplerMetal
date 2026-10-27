# SPDX-License-Identifier: MIT
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge/tools'))
from verify_partial_range_chain import N, expected


class PartialRangeChainOracleTests(unittest.TestCase):
    def test_producer_and_order_change_consumer(self):
        blank = expected(0, False)
        forward = expected(1, True)
        missing = expected(4, True)
        reverse = expected(5, True)
        self.assertEqual(forward['a'], blank['a'])
        self.assertEqual(forward['b'], reverse['b'])
        self.assertEqual(missing['c'], reverse['c'])
        self.assertNotEqual(forward['c'], missing['c'])
        self.assertEqual(struct.unpack_from('<I', missing['count1'], 64)[0], 0)
        self.assertEqual(struct.unpack_from('<I', missing['count2'], 64)[0], N)
        for record in (blank, forward, missing, reverse):
            for value in record.values():
                self.assertEqual(value[:64], b'\xa5' * 64)
                self.assertEqual(value[-64:], b'\xa5' * 64)

    def test_three_dimensional_limit_keeps_wrap_and_guards(self):
        n = 11 * 7 * 5
        forward = expected(1, True, n)
        reverse = expected(5, True, n)
        self.assertEqual(len(forward['a']), 64 + n * 16 + 64)
        self.assertEqual(forward['b'], reverse['b'])
        self.assertNotEqual(forward['c'], reverse['c'])
        self.assertEqual(struct.unpack_from('<I', forward['count1'], 64)[0], n)
        self.assertEqual(forward['c'][-64:], b'\xa5' * 64)


if __name__ == '__main__':
    unittest.main()
