"""Portable numerical cross-checks; importing these modules performs no GPU work."""
from pathlib import Path
import random
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "bridge/tools"))
from native_segmented_control import result_for_segments, iterative_result, SEGMENTS
from verify_control_flow import result as previous_result


class SegmentedControlTests(unittest.TestCase):
    def test_single_segment_matches_previous_nested_oracle(self):
        for levels in [0, 4, 64, 96, 120]:
            for gid in [0, 1, 31, 32, 98]:
                for seed in [0, 1, 0x13579, 0xffffffff]:
                    for reserved in [0, 1, 2]:
                        pieces = [levels] if levels else []
                        expected = previous_result(levels, gid, seed, reserved)
                        self.assertEqual(result_for_segments(pieces, gid, seed, reserved), expected)
                        self.assertEqual(iterative_result(pieces, gid, seed, reserved), expected)

    def test_unit_segments_match_previous_serial_oracle(self):
        for levels in [32, 64, 96, 120]:
            for gid in [0, 1, 31, 32, 98]:
                for seed in [0, 1, 0x13579, 0xffffffff]:
                    for reserved in [0, 1, 2]:
                        expected = previous_result(levels, gid, seed, reserved, serial=True)
                        self.assertEqual(result_for_segments([1] * levels, gid, seed, reserved), expected)
                        self.assertEqual(iterative_result([1] * levels, gid, seed, reserved), expected)

    def test_qualified_vectors_distinguish_full_and_segmented_control(self):
        for total, pieces in SEGMENTS.items():
            for trial in range(3):
                seed, reserved = 0x13579 + trial * 971, trial % 3
                for gid in range(99):
                    expected = result_for_segments(pieces, gid, seed, reserved)
                    self.assertEqual(iterative_result(pieces, gid, seed, reserved), expected)
                    self.assertNotEqual(previous_result(total, gid, seed, reserved), expected)

    def test_other_partitions_have_bounded_matching_results(self):
        rng = random.Random(0x880)
        for k in range(100):
            remaining = rng.randrange(1, 121)
            pieces = []
            while remaining:
                length = rng.randrange(1, min(65, remaining) + 1)
                pieces.append(length)
                remaining -= length
            gid, seed, reserved = rng.randrange(99), rng.randrange(1 << 32), k % 3
            expected = result_for_segments(pieces, gid, seed, reserved)
            self.assertEqual(iterative_result(pieces, gid, seed, reserved), expected)
            self.assertGreaterEqual(expected[2], sum(pieces))
            self.assertLessEqual(expected[2], sum(pieces) * 2)


if __name__ == "__main__":
    unittest.main()
