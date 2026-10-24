# SPDX-License-Identifier: MIT
import hashlib
import json
from pathlib import Path
import sys
import struct
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bridge/tools'))
from lower_air_render_reset import lower,normalized,IR_SHA256,helper
from verify_air_render_reset import expected,CASES,parse_reset_native


class AIRResetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ir=json.loads((ROOT/'tests/fixtures/air_render_reset_ir.json').read_text())['IR']

    def test_exact_profile(self):
        self.assertEqual(hashlib.sha256(normalized(self.ir).encode()).hexdigest(),IR_SHA256)
        out=lower(self.ir)
        self.assertNotIn('air.command_buffer',out)
        self.assertNotIn('@air.reset_render_command',out)
        self.assertIn('tail call void @kp_reset_render_command',out)
        self.assertEqual(out.count('store <4 x i32> zeroinitializer'),4)

    def test_body_load_preserved(self):
        out=lower(self.ir)
        for line in self.ir.splitlines():
            if '%3 = getelementptr' in line or '%4 = load' in line:self.assertIn(line,out)

    def test_other_module_path_allowed(self):
        self.assertEqual(lower(self.ir),lower(self.ir.replace('input.air','other.air',1)))

    def test_bad_identifier_refused(self):
        with self.assertRaises(ValueError):lower(self.ir.replace('; ModuleID','; unknown',1))

    def test_changed_operation_refused(self):
        with self.assertRaises(ValueError):lower(self.ir.replace('air.reset_render_command','air.reset_compute_command'))

    def test_changed_layout_refused(self):
        with self.assertRaises(ValueError):lower(self.ir.replace('i32 8, !"air.location_index"','i32 16, !"air.location_index"'))

    def test_changed_body_refused(self):
        with self.assertRaises(ValueError):lower(self.ir.replace('i32 %1) #2','i32 0) #2'))

    def test_extra_function_refused(self):
        with self.assertRaises(ValueError):lower(self.ir+'define void @extra(){ret void}\n')

    def test_oversized_refused(self):
        with self.assertRaises(ValueError):lower(self.ir+' '*65536)

    def test_pointer_header_contract(self):
        text=helper()
        for value in ['1099511626752','i32 %v2, 16','i32 %v3, 64','i64 %v5, 0','i64 %v4, 15']:
            self.assertIn(value,text)

    def test_prefix_and_bounds_oracle(self):
        data=expected(*CASES[0],True)
        self.assertEqual(data[64:256],bytes(192))
        self.assertEqual(data[:64],b'\xa5'*64)
        self.assertNotEqual(data[256:320],bytes(64))
        data=expected(*CASES[4],True)
        self.assertEqual(data[64:320],bytes(256))
        self.assertNotEqual(data[320:384],bytes(64))

    def test_invalid_contexts_unchanged(self):
        for case in CASES[6:]:
            self.assertEqual(expected(*case,True),expected(*case,False),case[0])

    def test_no_dispatch_control(self):
        for case in CASES:
            self.assertEqual(len(expected(*case,False)),1152)
        self.assertNotEqual(expected(*CASES[1],True),expected(*CASES[1],False))

    def test_unknown_case_refused(self):
        with self.assertRaises(AssertionError):expected('unknown',16,1,32,True)

    def test_frozen_geometry_refused(self):
        with self.assertRaises(AssertionError):expected('prefix',16,4,1,True)

    @staticmethod
    def payload():
        parts=[(1,struct.pack('<I',5)),(0x10004,bytes(232)),(0x10000,bytes(56)),
               (0x10001,bytes(32)),(0x10002,bytes(8)),(0x10003,bytes(32)),
               (0x10005,bytes(64)),(0x10006,bytes(4))]
        body=bytearray()
        for i,(kind,data)in enumerate(parts):
            n=(16+len(data)+7)&~7
            body+=struct.pack('<QII',n if i<7 else 0,kind,len(data))+data+bytes(n-16-len(data))
        return bytearray(struct.pack('<II',8,8+len(body))+body)

    def test_aligned_payload(self):
        code,meta=parse_reset_native(self.payload())
        self.assertEqual(code,bytes(64));self.assertEqual(meta,[0]*58)

    def test_nonzero_final_padding_refused(self):
        data=self.payload();data[-1]=1
        with self.assertRaises(AssertionError):parse_reset_native(data)

    def test_nonzero_section_padding_refused(self):
        data=self.payload();data[28]=1
        with self.assertRaises(AssertionError):parse_reset_native(data)

    def test_trailing_section_refused(self):
        data=self.payload()+bytes(8);struct.pack_into('<I',data,4,len(data))
        with self.assertRaises(AssertionError):parse_reset_native(data)

    def test_bad_link_refused(self):
        data=self.payload();struct.pack_into('<Q',data,8,32)
        with self.assertRaises(AssertionError):parse_reset_native(data)

    def test_wrong_stage_refused(self):
        data=self.payload();struct.pack_into('<I',data,24,1)
        with self.assertRaises(AssertionError):parse_reset_native(data)

if __name__=='__main__':unittest.main()
