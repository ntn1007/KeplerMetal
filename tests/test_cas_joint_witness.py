"""CPU-only acceptance and corruption tests for correlated CAS markers."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge/experiments/cas_divergence'))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_cas_branch_witness import fixture
from verify_joint_witness import compare

class JointWitness(unittest.TestCase):
    def test_valid_markers(self):
        for pattern, markers in ((0, (2,)), (2, (0x98, 0x99)), (3, (0xb8, 0xb9)), (4, (0x30, 0x31))):
            baseline, br, trace, tr = fixture(pattern)
            trace = bytearray(trace)
            for i in range(99):
                struct.pack_into('<I', trace, 68 + 16 * i, markers[i % len(markers)])
            result = compare(baseline, br, bytes(trace), tr)
            self.assertEqual(sum(result['markers'].values()), 99)

    def test_guard_marker_or_other_component_corruption_fails(self):
        for offset in (0, 64, 68, 72, 76):
            baseline, br, trace, tr = fixture(0)
            trace = bytearray(trace)
            for i in range(99):
                struct.pack_into('<I', trace, 68 + 16 * i, 2)
            if offset == 68:
                struct.pack_into('<I', trace, offset, 7)
            else:
                trace[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaises(ValueError):
                compare(baseline, br, bytes(trace), tr)

if __name__ == '__main__':
    unittest.main()
