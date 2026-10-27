# SPDX-License-Identifier: MIT
import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/tools'))
from verify_partial_assembly_3d import expected_outputs,pack

class Assembly3DOracleTests(unittest.TestCase):
 def test_regions_partition_and_complete_reference(self):
  controls=[expected_outputs(i) for i in range(1,9)];total=sum(v[3] for v in controls)
  self.assertEqual(total,385);self.assertEqual([v[3] for v in controls],[96,64,72,48,36,24,27,18])
  c,g,counter,n=expected_outputs(9);self.assertEqual(n,385);self.assertEqual(expected_outputs(9),expected_outputs(10))
  self.assertEqual(struct.unpack_from('<4I',c,64+384*16),(pack((10,6,4)),pack((2,2,1)),pack((2,1,1)),pack((3,2,2))))
  self.assertEqual(struct.unpack_from('<3I',g,64+384*16),(pack((3,3,2)),pack((4,4,3)),pack((11,7,5))))
  self.assertEqual(struct.unpack_from('<I',counter,64)[0],385)
  for index in range(385):
   rows=[v[0][64+index*16:80+index*16] for v in controls];written=[x for x in rows if x!=b'\xa5'*16]
   self.assertEqual(len(written),1);self.assertEqual(written[0],c[64+index*16:80+index*16])
  none,_,_,n=expected_outputs(0);self.assertEqual(n,0);self.assertEqual(none,b'\xa5'*len(none));self.assertEqual(c[-64:],b'\xa5'*64)
 def test_rejects_unknown(self):
  with self.assertRaises(ValueError):expected_outputs(11)
