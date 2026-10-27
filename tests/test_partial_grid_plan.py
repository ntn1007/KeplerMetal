# SPDX-License-Identifier: MIT
import itertools,math,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/tools'))
from partial_grid_plan import plan

class PartialGridPlanTests(unittest.TestCase):
    def test_exhaustive_small_geometry_matches_independent_thread_model(self):
        for grid in itertools.product(range(1,6),repeat=3):
            for local in itertools.product(range(1,5),repeat=3):
                result=plan(grid,local,125);seen={};groups=tuple((g+l-1)//l for g,l in zip(grid,local))
                self.assertFalse(result['safe_to_dispatch']);self.assertFalse(result['encoder_implemented']);self.assertLessEqual(len(result['segments']),8)
                for s in result['segments']:
                    for ct in itertools.product(*(range(n) for n in s['physical_group_count'])):
                        group=tuple(a+b for a,b in zip(s['group_base'],ct));actual=tuple(min(l,g-b*l) for g,l,b in zip(grid,local,group));self.assertEqual(tuple(s['actual_local']),actual)
                        for lane in itertools.product(*(range(n) for n in actual)):
                            gid=tuple(o+c*l+t for o,c,l,t in zip(s['thread_origin'],ct,actual,lane));self.assertNotIn(gid,seen);seen[gid]=(group,lane,actual)
                self.assertEqual(len(seen),math.prod(grid));self.assertEqual(tuple(result['logical_group_count']),groups)
                for gid in itertools.product(*(range(n) for n in grid)):
                    group=tuple(g//l for g,l in zip(gid,local));lane=tuple(g%l for g,l in zip(gid,local));actual=tuple(min(l,g-b*l) for g,l,b in zip(grid,local,group));self.assertEqual(seen[gid],(group,lane,actual))
    def test_edges_and_invalid_inputs_fail_closed(self):
        for g,l,b in [((0,1,1),(1,1,1),1),((True,1,1),(1,1,1),1),((1,1,1),(0,1,1),1),((1,1,1),(1,1,65),1),((1,1,1),(33,32,1),1),((2,2,2),(1,1,1),7),((1,65536,1),(1,1,1),65536),((1,1,1),(1,1,1),0)]:
            with self.subTest(grid=g,local=l,bound=b),self.assertRaises(ValueError):plan(g,l,b)
        r=plan((11,7,5),(4,4,3),385);self.assertEqual(len(r['segments']),8);self.assertEqual(r['logical_group_count'],[3,2,2])
        r=plan((2**31-1,1,1),(1,1,1),2**31-1);self.assertEqual(r['segments'][0]['physical_group_count'],[2**31-1,1,1])
if __name__=='__main__':unittest.main()
