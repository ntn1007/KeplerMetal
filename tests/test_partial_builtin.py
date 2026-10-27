# SPDX-License-Identifier: MIT
import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/tools'))
from verify_partial_builtin import expected_outputs,pack

class BuiltinOracleTests(unittest.TestCase):
 def test_edge_fields_and_neighbor_barrier(self):
  for node,origin,index,group,groups,actual,nominal,grid,count in [
   (0,(8,0,0),8,(2,0,0),(3,1,1),(3,1,1),(4,1,1),(11,1,1),3),
   (1,(0,4,0),32,(0,2,0),(2,3,1),(4,1,1),(4,2,1),(8,5,1),4),
   (2,(0,0,4),128,(0,0,2),(2,2,3),(4,2,1),(4,2,2),(8,4,5),8)]:
   coords,geometry,counter,n=expected_outputs(node,origin,False);seed=0x3141+101*node
   self.assertEqual(n,count)
   self.assertEqual(struct.unpack_from('<4I',coords,64+index*16),
                    (pack(origin),0,pack(group),pack(groups)))
   self.assertEqual(struct.unpack_from('<4I',geometry,64+index*16),
                    (pack(actual),pack(nominal),pack(grid),1^seed))
   self.assertEqual(struct.unpack_from('<I',counter,64)[0],count)
   self.assertEqual(coords[:64],b'\xa5'*64);self.assertEqual(geometry[-64:],b'\xa5'*64)
   blank,_,_,_=expected_outputs(node,origin,True);self.assertEqual(blank,b'\xa5'*len(blank))
 def test_rejects_unknown_geometry(self):
  with self.assertRaises(ValueError):expected_outputs(0,(7,0,0),False)
