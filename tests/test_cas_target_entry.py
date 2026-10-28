"""CPU-only counterexamples for target-entry witness comparisons."""
import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/experiments/cas_divergence'))
sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_target_entry import compare
from test_cas_branch_witness import fixture

class TargetEntry(unittest.TestCase):
    def test_entry_and_bypass_markers(self):
        for pattern,marker in ((0,1),(2,0),(3,0),(4,0)):
            b,br,t,tr=fixture(pattern);t=bytearray(t)
            for i in range(99):struct.pack_into('<I',t,68+16*i,marker)
            self.assertEqual(compare(b,br,bytes(t),tr)['markers'],{str(marker):99})

    def test_corrupt_marker_data_guard_and_baseline_refused(self):
        for offset in (0,64,68,72,76):
            b,br,t,tr=fixture(0);t=bytearray(t)
            if offset==68:struct.pack_into('<I',t,offset,7)
            else:t[offset]^=1
            with self.subTest(offset=offset),self.assertRaises(ValueError):compare(b,br,bytes(t),tr)
        b,br,t,tr=fixture(0);b=bytearray(b);b[64]^=1
        with self.assertRaises(ValueError):compare(bytes(b),br,t,tr)

if __name__=='__main__':unittest.main()
