# SPDX-License-Identifier: MIT
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge/tools'))
from verify_partial_stencil_api import CASES, expected_outputs


class PartialStencilOracleTests(unittest.TestCase):
    def test_immutable_source_wraparound_and_guards(self):
        for case, (grid, _, _) in enumerate(CASES):
            source, output, counter, n = expected_outputs(case, True)
            before, untouched, zero, inactive = expected_outputs(case, False)
            self.assertEqual(source, before)
            self.assertEqual(inactive, 0)
            self.assertEqual(untouched, b'\xa5' * len(untouched))
            self.assertEqual(struct.unpack_from('<I', zero, 64)[0], 0)
            self.assertEqual(n, grid[0] * grid[1] * grid[2])
            self.assertEqual(struct.unpack_from('<I', counter, 64)[0], n)
            self.assertEqual(source[:64], b'\xa5' * 64)
            self.assertEqual(output[64 + n * 16:], b'\xa5' * (len(output) - 64 - n * 16))
            first = (1 ^ (10 if n > 1 else 7) ^ 0x3141,
                     7 + ((1 ^ 0x12345) if n > 1 else 0x12345),
                     0x12345 ^ (24 if n > 1 else 11),
                     11 + (18 if n > 1 else 1) + 0x3141)
            self.assertEqual(struct.unpack_from('<4I', output, 64), first)
            last = struct.unpack_from('<4I', output, 64 + (n - 1) * 16)
            self.assertEqual(last, ((n - 1) * 17 + 1 ^ 7 ^ 0x3141,
                                    (n - 1) * 3 + 7 + 0x12345,
                                    ((n - 1) ^ 0x12345) ^ 11,
                                    (n - 1) * 13 + 11 + 1 + 0x3141))

    def test_invalid_case_refused(self):
        with self.assertRaises(ValueError):
            expected_outputs(8, True)
