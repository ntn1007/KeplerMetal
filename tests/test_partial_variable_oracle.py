# SPDX-License-Identifier: MIT
"""Cross-check the new buffer layout against the previous stencil oracle."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge/tools'))
from verify_partial_stencil_api import CASES, expected_outputs as previous
from verify_partial_variable_resources import expected_outputs as current
from verify_partial_general_api import expected_outputs as previous_barrier
from verify_partial_variable_barrier import expected_outputs as current_barrier


class VariableResourceOracleTests(unittest.TestCase):
    def test_layout_changes_do_not_change_values(self):
        for case, (grid, _, _) in enumerate(CASES):
            offset, counter_offset = (128, 32) if case % 2 else (512, 128)
            n = grid[0] * grid[1] * grid[2]
            for active in (False, True):
                with self.subTest(case=case, active=active):
                    old_source, old_output, old_counter, old_n = previous(case, active)
                    source, output, counter, new_n = current(case, active)
                    self.assertEqual(new_n, old_n)
                    self.assertEqual(source[offset:offset+n*16], old_source[64:64+n*16])
                    self.assertEqual(output[offset:offset+n*16], old_output[64:64+n*16])
                    self.assertEqual(struct.unpack_from('<I', counter, counter_offset),
                                     struct.unpack_from('<I', old_counter, 64))
                    for buf in (source, output):
                        self.assertEqual(buf[:offset], b'\xa5' * offset)
                        self.assertEqual(buf[offset+n*16:], b'\xa5' * 64)

    def test_barrier_layout_changes_preserve_old_oracle(self):
        for case, (grid, _, _) in enumerate(CASES):
            offset, counter_offset = (128, 32) if case % 2 else (512, 128)
            n = grid[0] * grid[1] * grid[2]
            for active in (False, True):
                old_a, old_b, old_counter, old_n = previous_barrier(case, active)
                a, b, counter, new_n = current_barrier(case, active)
                self.assertEqual(new_n, old_n)
                self.assertEqual(a[offset:offset+n*16], old_a[64:64+n*16])
                self.assertEqual(b[offset:offset+n*16], old_b[64:64+n*16])
                self.assertEqual(struct.unpack_from('<I', counter, counter_offset),
                                 struct.unpack_from('<I', old_counter, 64))
                for buf in (a, b):
                    self.assertEqual(buf[:offset], b'\xa5' * offset)
                    self.assertEqual(buf[offset+n*16:], b'\xa5' * 64)


if __name__ == '__main__':
    unittest.main()
