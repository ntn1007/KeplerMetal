# SPDX-License-Identifier: MIT
import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/tools'))
from verify_partial_origin import expected_outputs

class OriginOracleTests(unittest.TestCase):
 def test_three_axes_and_zero_controls(self):
  for node,origin,first,count in [(0,(8,0,0),8,8),(1,(0,4,0),32,32),(2,(0,0,4),128,128)]:
   coordinates,geometry,counter,n=expected_outputs(node,origin,False)
   self.assertEqual(n,count)
   self.assertEqual(struct.unpack_from('<4I',coordinates,64+16*first),(*origin,first))
   self.assertEqual(struct.unpack_from('<I',counter,64)[0],count)
   self.assertEqual(coordinates[:64],b'\xa5'*64)
   self.assertEqual(coordinates[64:64+16*first],b'\xa5'*(16*first))
   self.assertEqual(coordinates[-64:],b'\xa5'*64)
   blank,_,blank_counter,_=expected_outputs(node,origin,True)
   self.assertEqual(blank,b'\xa5'*len(blank))
   self.assertEqual(struct.unpack_from('<I',blank_counter,64)[0],0)
 def test_rejects_other_profiles(self):
  with self.assertRaises(ValueError):expected_outputs(0,(1,2,3),False)
  with self.assertRaises(ValueError):expected_outputs(3,(0,0,0),False)
