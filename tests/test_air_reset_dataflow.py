# SPDX-License-Identifier: MIT
import json
from pathlib import Path
import re
import struct
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'bridge/tools'))
from air_reset_lowering import lower,entry_body
from verify_air_reset_dataflow import expected,CASES


class StructuralResetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.simple=json.loads((ROOT/'tests/fixtures/air_render_reset_ir.json').read_text())['IR']
        cls.rich=json.loads((ROOT/'tests/fixtures/air_reset_dataflow_ir.json').read_text())['IR']

    def test_two_distinct_entries(self):
        self.assertNotEqual(entry_body(self.simple),entry_body(self.rich))
        for ir in [self.simple,self.rich]:
            self.assertEqual(entry_body(lower(ir)),entry_body(ir).replace('@air.reset_render_command','@kp_reset_render_command'))

    def test_metadata_number_independence(self):
        ir=re.sub(r'!(\d+)',lambda m:'!'+str(int(m[1])+1000),self.rich)
        self.assertEqual(entry_body(lower(ir)),re.sub(r'!(\d+)',lambda m:'!'+str(int(m[1])+1000),entry_body(lower(self.rich))))
        self.assertNotIn('air.command_buffer',lower(ir))

    def test_ordinary_argument_metadata_preserved(self):
        for line in self.rich.splitlines():
            if '!"air.arg_name", !"out"'in line or '!"air.arg_name", !"indices"'in line or '!"air.arg_name", !"config"'in line:
                self.assertIn(line,lower(self.rich))

    def test_missing_operation_refused(self):
        with self.assertRaises(ValueError):lower(self.rich.replace('air.reset_render_command','air.reset_compute_command'))

    def test_wrong_binding_refused(self):
        with self.assertRaises(ValueError):lower(self.rich.replace('!"air.location_index", i32 0, i32 1','!"air.location_index", i32 7, i32 1'))

    def test_wrong_root_size_refused(self):
        with self.assertRaises(ValueError):lower(self.rich.replace('!"air.buffer_size", i32 8','!"air.buffer_size", i32 16'))

    def test_duplicate_node_refused(self):
        with self.assertRaises(ValueError):lower(self.rich+'!18 = !{}\n')

    def test_shared_leaf_refused(self):
        with self.assertRaises(ValueError):lower(self.rich+'!999 = !{!20}\n')

    def test_helper_collision_refused(self):
        with self.assertRaises(ValueError):lower(self.rich+'; @kp_reset_render_command\n')

    def test_other_command_refused(self):
        with self.assertRaises(ValueError):lower(self.rich+'declare void @air.copy_render_command()\n')

    def test_both_branch_paths_observed(self):
        case=next(c for c in CASES if c[0]=='branch');_,slots=expected(case,True)
        self.assertEqual(len(slots),8)

    def test_mask_and_capacity(self):
        case=next(c for c in CASES if c[0]=='mask3');_,slots=expected(case,True)
        self.assertGreater(len(slots),0);self.assertLess(len(slots),7)
        self.assertTrue(all(s<7 for s in slots))

    def test_no_duplicate_writers(self):
        for case in CASES:
            _,slots=expected(case,True);self.assertEqual(len(slots),len(set(slots)))

    def test_invalid_context_keeps_arithmetic(self):
        for case in CASES[7:]:
            data,slots=expected(case,True);before,_=expected(case,False)
            self.assertEqual(slots,[]);self.assertEqual(data[0],before[0]);self.assertNotEqual(data[1],before[1])

    def test_empty_has_no_witness(self):
        self.assertEqual(expected(CASES[0],True)[0],expected(CASES[0],False)[0])

    def test_tail_and_all_guards(self):
        for case in CASES:
            data,_=expected(case,True);before,_=expected(case,False)
            for a,b in zip(data,before):self.assertEqual(a[:64]+a[-64:],b[:64]+b[-64:])
            self.assertEqual(data[1][64+case[1]*4:],before[1][64+case[1]*4:])
            self.assertEqual(data[2],before[2])

    def test_unknown_recipe_refused(self):
        with self.assertRaises(AssertionError):expected(('unknown',1,1,0,0,1),True)

if __name__=='__main__':unittest.main()
