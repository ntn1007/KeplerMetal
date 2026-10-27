# SPDX-License-Identifier: MIT
"""Bounded fragment AIR translation checks; no GPU execution is implied."""
import json
from pathlib import Path
import re
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bridge/tools'))
from air_fragment_binding_lowering import lower,SET,FRAGMENT_MAGIC
from air_reset_lowering import entry_body


class FragmentLowering(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.ir=json.loads((ROOT/'tests/fixtures/air_fragment_binding_ir.json').read_text())['IR']

 def test_entry_dataflow_and_order(self):
  expected=entry_body(self.ir).replace('@'+SET,'@kp_set_fragment_buffer').replace('@air.draw_primitives_render_command','@kp_draw_primitives_render_command')
  self.assertEqual(entry_body(lower(self.ir)),expected)
  self.assertLess(expected.index('@kp_set_fragment_buffer'),expected.index('@kp_draw_primitives_render_command'))

 def test_pointer_is_compared_and_header_is_distinct(self):
  text=lower(self.ir);self.assertIn('ptrtoint i8 addrspace(1)* %buffer to i64',text)
  self.assertIn('%emagic = icmp eq i32 %e0, '+str(FRAGMENT_MAGIC),text)
  self.assertNotRegex(text,r'load [^\n]*\* %buffer,')

 def test_unknown_operations_and_non_device_pointer_refused(self):
  with self.assertRaises(ValueError):lower(self.ir+'\ndeclare void @air.set_vertex_buffer_render_command()\n')
  with self.assertRaises(ValueError):lower(self.ir.replace('p1i8','p2i8').replace('i8 addrspace(1)*','i8 addrspace(2)*'))
  with self.assertRaises(ValueError):lower(self.ir.replace('!"air.buffer_size", i32 8','!"air.buffer_size", i32 16'))

 def test_metadata_renumbering(self):
  modified=re.sub(r'!(\d+)',lambda m:'!'+str(int(m[1])+100),self.ir)
  self.assertEqual(entry_body(lower(modified)),re.sub(r'!(\d+)',lambda m:'!'+str(int(m[1])+100),entry_body(lower(self.ir))))
