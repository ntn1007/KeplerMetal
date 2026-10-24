# SPDX-License-Identifier: MIT
import json
from pathlib import Path
import re
import struct
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'bridge/tools'))
from air_render_draw_lowering import lower,DRAW,RESET
from air_reset_lowering import entry_body
from verify_air_render_draw import expected,CASES


class TypedRenderDraw(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.ir=json.loads((ROOT/'tests/fixtures/air_render_draw_ir.json').read_text())['IR']

    def test_entry_only_changes_command_callees(self):
        want=entry_body(self.ir).replace('@'+DRAW,'@kp_draw_primitives_render_command').replace('@'+RESET,'@kp_reset_render_command')
        self.assertEqual(entry_body(lower(self.ir)),want)

    def test_ordinary_metadata_stays_native(self):
        for line in self.ir.splitlines():
            if any('!"air.arg_name", !"'+n+'"'in line for n in ['out','indices','config','gid']):self.assertIn(line,lower(self.ir))

    def test_metadata_graph_renumbering(self):
        changed=re.sub(r'!(\d+)',lambda m:'!'+str(int(m[1])+1000),self.ir)
        self.assertEqual(entry_body(lower(changed)),re.sub(r'!(\d+)',lambda m:'!'+str(int(m[1])+1000),entry_body(lower(self.ir))))

    def test_other_primitive_refused(self):
        line=next(s for s in self.ir.splitlines()if'call void @'+DRAW in s)
        with self.assertRaises(ValueError):lower(self.ir.replace(line,line.replace(', i32 3,',', i32 1,',1)))

    def test_dynamic_primitive_refused(self):
        line=next(s for s in self.ir.splitlines()if'call void @'+DRAW in s)
        with self.assertRaises(ValueError):lower(self.ir.replace(line,line.replace(', i32 3,',', i32 %1000,',1)))

    def test_indexed_draw_not_silently_accepted(self):
        with self.assertRaises(ValueError):lower(self.ir.replace(DRAW,'air.draw_indexed_primitives_render_command'))

    def test_draw_declaration_shape_required(self):
        line=next(s for s in self.ir.splitlines()if s.startswith('declare void @'+DRAW))
        with self.assertRaises(ValueError):lower(self.ir.replace(line,line.replace(', i32)',', i64)')))

    def test_wrong_root_or_helper_collision_refused(self):
        for changed in [self.ir.replace('!"air.buffer_size", i32 8','!"air.buffer_size", i32 16'),self.ir+'; @kp_fake\n']:
            with self.assertRaises(ValueError):lower(changed)

    def test_reset_only_still_requires_other_profile(self):
        ir=json.loads((ROOT/'tests/fixtures/air_reset_dataflow_ir.json').read_text())['IR']
        with self.assertRaises(ValueError):lower(ir)

    def test_order_changes_only_records_not_arithmetic(self):
        rows={c[0]:expected(c,True)[0]for c in CASES[-3:]}
        self.assertEqual(rows['draw_only'][1:],rows['ordered_draw'][1:])
        self.assertEqual(rows['draw_only'][1:],rows['ordered_reset'][1:])
        self.assertNotEqual(rows['draw_only'][0],rows['ordered_draw'][0])
        self.assertEqual(rows['ordered_reset'][0][64:-64],bytes(1024))
        for i in range(16):
            a=struct.unpack_from('<8IQ6I',rows['draw_only'][0],64+i*64)
            b=struct.unpack_from('<8IQ6I',rows['ordered_draw'][0],64+i*64)
            self.assertEqual(a[:8]+a[9:],b[:8]+b[9:]);self.assertNotEqual(a[8],0);self.assertEqual(b[8],0)

    def test_invalid_context_preserves_records_and_produces_witness(self):
        for case in CASES[7:16]:
            a,slots=expected(case,True);b,_=expected(case,False)
            self.assertEqual(slots,[]);self.assertEqual(a[0],b[0]);self.assertNotEqual(a[1],b[1])

    def test_guards_indices_and_one_writer(self):
        for case in CASES:
            a,slots=expected(case,True);b,_=expected(case,False)
            self.assertEqual(len(slots),len(set(slots)));self.assertEqual(a[2],b[2])
            for x,y in zip(a,b):self.assertEqual(x[:64]+x[-64:],y[:64]+y[-64:])
            self.assertEqual(a[1][64+4*case[1]:],b[1][64+4*case[1]:])

    def test_unknown_recipe_refused(self):
        with self.assertRaises(AssertionError):expected(('unknown',16,16,3,0,32),True)


if __name__=='__main__':unittest.main()
