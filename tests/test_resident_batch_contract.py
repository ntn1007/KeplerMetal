# SPDX-License-Identifier: MIT
"""CPU-only controls of the independent batch ordering/alias oracle."""
import copy
import unittest
from pathlib import Path
import importlib.util
_module=Path(__file__).resolve().parents[1]/'tools/resident_batch_contract.py'
_spec=importlib.util.spec_from_file_location('batch_contract',_module)
_contract=importlib.util.module_from_spec(_spec);_spec.loader.exec_module(_contract)
POISON,check_plan,oracle,witness=_contract.POISON,_contract.check_plan,_contract.oracle,_contract.witness

def plan(barriers):
    rows=[]
    for i in range(4):
        rows.append(dict(descriptor=0x200000+0x1000*i,ranges=[dict(binding=0,access='atomic',begin=0x100000,end=0x10000c),
            dict(binding=1,access='write',begin=0x110000+64*i,end=0x110020+64*i),dict(binding=2,access='read',begin=0x120000+64*i,end=0x120010+64*i)]))
    return dict(record_indices=[0,1,2,3],barrier_before_positions=barriers,footprints=rows)

def row(tags):
    nonce=710011;s=[POISON]*256;o=[POISON]*512;s[64:67]=[8,1,1];results=[]
    for i,(begin,end) in enumerate(tags):
        n=nonce+37*i;o[64*(i+1):64*(i+1)+8]=[begin,end,1,1,oracle(n,i%2),n,i%2,128]
        results.append(dict(index=i,begin=begin,end=end,seen=1,iterations=1,arithmetic=oracle(n,i%2)))
    overlap=crossed=0
    for i,(a,b) in enumerate(tags):
        for j,(c,d) in enumerate(tags[i+1:],i+1):overlap+=a<d and c<b;crossed+=i<2<=j and b>=c
    return dict(sync_words=s,output_words=o,results=results,arithmetic_mismatches=0,guard_mismatches=0,active_dispatches=4,interleaved_pairs=overlap,crossed_midpoint_pairs=crossed)

class ResidentBatchOracle(unittest.TestCase):
    def test_all_eight_barrier_masks_allow_disjoint_footprints(self):
        for mask in range(8):
            b=[i+1 for i in range(3) if mask&(1<<i)];check_plan(plan(b),[0,1,2,3],b)
    def test_output_alias_requires_a_boundary(self):
        p=plan([]);p['footprints'][1]['ranges'][1]=copy.deepcopy(p['footprints'][0]['ranges'][1])
        with self.assertRaises(ValueError):check_plan(p,[0,1,2,3],[])
        p['barrier_before_positions']=[1];check_plan(p,[0,1,2,3],[1])
    def test_partial_atomic_alias_is_not_atomic_sharing(self):
        p=plan([]);p['footprints'][1]['ranges'][0]['begin']+=4;p['footprints'][1]['ranges'][0]['end']+=4
        with self.assertRaises(ValueError):check_plan(p,[0,1,2,3],[])
    def test_self_alias_is_refused_even_with_serial_boundaries(self):
        p=plan([1,2,3]);a=p['footprints'][0]['ranges'][1];a['begin']=0x100000;a['end']=0x100020
        with self.assertRaises(ValueError):check_plan(p,[0,1,2,3],[1,2,3])
    def test_serial_tags_satisfy_every_boundary_mask(self):
        r=row([(1,2),(3,4),(5,6),(7,8)])
        for mask in range(8):witness(r,[0,1,2,3],[i+1 for i in range(3) if mask&(1<<i)],710011)
    def test_all_interleaved_tags_require_no_boundary(self):
        r=row([(1,5),(2,6),(3,7),(4,8)]);witness(r,[0,1,2,3],[],710011)
        for i in range(1,4):
            with self.assertRaises(ValueError):witness(r,[0,1,2,3],[i],710011)
    def test_segmented_tags_preserve_only_the_correct_boundary(self):
        r=row([(1,3),(2,4),(5,7),(6,8)]);witness(r,[0,1,2,3],[2],710011)
        for i in [1,3]:
            with self.assertRaises(ValueError):witness(r,[0,1,2,3],[i],710011)
    def test_raw_guard_corruption_is_refused(self):
        r=row([(1,3),(2,4),(5,7),(6,8)]);r['output_words'][0]=0
        with self.assertRaises(ValueError):witness(r,[0,1,2,3],[2],710011)
    def test_raw_arithmetic_corruption_is_refused(self):
        r=row([(1,3),(2,4),(5,7),(6,8)]);r['output_words'][68]^=1
        with self.assertRaises(ValueError):witness(r,[0,1,2,3],[2],710011)

if __name__=='__main__':unittest.main()
