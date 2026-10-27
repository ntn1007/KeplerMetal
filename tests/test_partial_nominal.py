# SPDX-License-Identifier: MIT
import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/tools'))
from verify_partial_nominal import expected_outputs,pack

class NominalOracleTests(unittest.TestCase):
 def test_logical_group_count_and_actual_group_size(self):
  # One physical CTA models each edge; index is shader-specific, not a linear
  # index in the logical grid. The nominal divisor must differ from local size.
  for node,origin,index,group,groups,local,count in [
   (0,(8,0,0),8,(2,0,0),(3,1,1),(3,1,1),3),
   (1,(0,4,0),32,(0,2,0),(2,3,1),(4,1,1),4),
   (2,(0,0,4),128,(0,0,2),(2,2,3),(4,2,1),8)]:
   coords,geometry,counter,n=expected_outputs(node,origin,False)
   self.assertEqual(n,count)
   self.assertEqual(struct.unpack_from('<4I',coords,64+index*16),(*origin,index))
   self.assertEqual(struct.unpack_from('<4I',geometry,64+index*16),
                    (0,pack(group),pack(groups),pack(local)^(0x3141+101*node)))
   self.assertEqual(struct.unpack_from('<I',counter,64)[0],count)
   self.assertEqual(coords[:64],b'\xa5'*64)
   self.assertEqual(coords[-64:],b'\xa5'*64)
   none,_,c,_=expected_outputs(node,origin,True)
   self.assertEqual(none,b'\xa5'*len(none))
   self.assertEqual(struct.unpack_from('<I',c,64)[0],0)
 def test_refuses_unqualified_geometry(self):
  with self.assertRaises(ValueError):expected_outputs(0,(7,0,0),False)
  with self.assertRaises(ValueError):expected_outputs(3,(0,0,0),False)
