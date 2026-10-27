# SPDX-License-Identifier: MIT
import struct,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/tools'))
from verify_partial_general_api import CASES,expected_outputs,pack
from verify_partial_general_extra import CASES as EXTRA,expected_outputs as expected_extra
from verify_partial_general_limit import CASES as LIMIT,expected_outputs as expected_limit
class GeneralPartialOracleTests(unittest.TestCase):
 def test_bounds_controls_and_last_thread(self):
  for i,(grid,local,_) in enumerate(CASES):
   c,g,counter,n=expected_outputs(i,True);blank,_,zero,z=expected_outputs(i,False)
   self.assertEqual(z,0);self.assertEqual(blank,b'\xa5'*len(blank));self.assertEqual(struct.unpack_from('<I',zero,64)[0],0)
   self.assertEqual(n,grid[0]*grid[1]*grid[2]);last=tuple(x-1 for x in grid);group=tuple(x//l for x,l in zip(last,local));lane=tuple(x%l for x,l in zip(last,local));groups=tuple((x+l-1)//l for x,l in zip(grid,local));actual=tuple(min(l,x-k*l) for x,l,k in zip(grid,local,group))
   self.assertEqual(struct.unpack_from('<4I',c,64+(n-1)*16),(pack(last),pack(lane),pack(group),pack(groups)))
   self.assertEqual(struct.unpack_from('<3I',g,64+(n-1)*16),(pack(actual),pack(local),pack(grid)))
   self.assertEqual(c[:64],b'\xa5'*64);self.assertEqual(g[-64:],b'\xa5'*64);self.assertEqual(struct.unpack_from('<I',counter,64)[0],n)
 def test_extra_axis_and_three_dimensional_cases(self):
  for i,(grid,local,regions) in enumerate(EXTRA):
   coords,geometry,counter,n=expected_extra(i,True);self.assertEqual(n,grid[0]*grid[1]*grid[2]);self.assertLessEqual(regions,16)
   last=tuple(v-1 for v in grid);group=tuple(v//l for v,l in zip(last,local));lane=tuple(v%l for v,l in zip(last,local));groups=tuple((v+l-1)//l for v,l in zip(grid,local));actual=tuple(min(l,v-k*l) for v,l,k in zip(grid,local,group))
   self.assertEqual(struct.unpack_from('<4I',coords,64+16*(n-1)),(pack(last),pack(lane),pack(group),pack(groups)))
   self.assertEqual(struct.unpack_from('<3I',geometry,64+16*(n-1)),(pack(actual),pack(local),pack(grid)));self.assertEqual(struct.unpack_from('<I',counter,64)[0],n)
 def test_sixteen_region_boundary_reference(self):
  grid,local,regions=LIMIT[0];self.assertEqual(regions,16);coords,geometry,counter,n=expected_limit(0,True);self.assertEqual(n,966)
  last=tuple(v-1 for v in grid);group=tuple(v//l for v,l in zip(last,local));lane=tuple(v%l for v,l in zip(last,local));groups=tuple((v+l-1)//l for v,l in zip(grid,local))
  self.assertEqual(struct.unpack_from('<4I',coords,64+16*(n-1)),(pack(last),pack(lane),pack(group),pack(groups)));self.assertEqual(struct.unpack_from('<I',counter,64)[0],966)
 def test_unknown_case_refused(self):
  with self.assertRaises(ValueError):expected_outputs(8,True)
