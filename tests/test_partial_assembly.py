# SPDX-License-Identifier: MIT
import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/tools'))
from verify_partial_assembly import expected_outputs,pack

class PartialAssemblyOracleTests(unittest.TestCase):
 def test_combined_grid_and_region_controls(self):
  blank,_,c,n=expected_outputs(0);self.assertEqual(n,0);self.assertEqual(blank,b'\xa5'*len(blank));self.assertEqual(struct.unpack_from('<I',c,64)[0],0)
  full,_,_,n=expected_outputs(1);self.assertEqual(n,128);self.assertEqual(full[64+128*16:64+191*16],b'\xa5'*(63*16))
  edge,_,_,n=expected_outputs(2);self.assertEqual(n,63);self.assertEqual(edge[64:64+128*16],b'\xa5'*(128*16))
  coord,geometry,c,n=expected_outputs(3);self.assertEqual(n,191)
  self.assertEqual(struct.unpack_from('<4I',coord,64+128*16),(128,0,2,pack((3,1,1))))
  self.assertEqual(struct.unpack_from('<4I',geometry,64+128*16),(pack((63,1,1)),pack((64,1,1)),pack((191,1,1)),32^0x3141))
  self.assertEqual(expected_outputs(3),expected_outputs(4));self.assertEqual(struct.unpack_from('<I',c,64)[0],191)
  self.assertEqual(coord[:64],b'\xa5'*64);self.assertEqual(coord[-64:],b'\xa5'*64)
 def test_unqualified_trial_rejected(self):
  with self.assertRaises(ValueError):expected_outputs(5)
