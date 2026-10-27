# SPDX-License-Identifier: MIT
"""Structural compilation checks only; no GPU execution is implied."""
import json,re,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bridge/tools'))
from air_quad_render_lowering import lower,VERTEX,PIPELINE,FRAGMENT,INDEXED
from air_reset_lowering import entry_body
class QuadRenderLowering(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.ir=json.loads((ROOT/'tests/fixtures/air_quad_render_ir.json').read_text())['IR']
 def test_entry_dataflow_and_command_order(self):
  expected=entry_body(self.ir)
  for src,dst in ((VERTEX,'kp_set_vertex_buffer'),(PIPELINE,'kp_set_render_pipeline'),(FRAGMENT,'kp_set_fragment_buffer'),('air.reset_render_command','kp_reset_render_command')):expected=expected.replace('@'+src,'@'+dst)
  for bits,name in INDEXED.items():expected=expected.replace('@'+name,'@kp_indexed_render_'+str(bits))
  self.assertEqual(entry_body(lower(self.ir)),expected)
 def test_fragment_walks_all_four_validated_headers(self):
  body=lower(self.ir).split('define internal void @kp_set_fragment_buffer(',1)[1].split('\n}',1)[0]
  markers=['%imagic = icmp eq i32','%vmagic = icmp eq i32','%pmagic = icmp eq i32','%fmagic = icmp eq i32']
  for m in markers:self.assertIn(m,body)
  self.assertEqual([body.index(m) for m in markers],sorted(body.index(m) for m in markers))
  for m in ('%fcounthigh = icmp ule i32 %fe2, 64','%ftableok = icmp eq i64','%bindingok = icmp eq i32 %b4, %binding','ptrtoint i8 addrspace(1)* %buffer to i64'):self.assertIn(m,body)
  self.assertNotRegex(body,r'load [^\n]*\* %buffer,')
 def test_unknown_operations_and_wrong_root_rejected(self):
  with self.assertRaises(ValueError):lower(self.ir+'\ndeclare void @air.unknown_render_command()\n')
  with self.assertRaises(ValueError):lower(self.ir.replace('!"air.buffer_size", i32 16','!"air.buffer_size", i32 8'))
  with self.assertRaises(ValueError):lower(self.ir.replace('@'+FRAGMENT,'@air.unknown_render_command'))
 def test_metadata_renumbering(self):
  changed=re.sub(r'!(\d+)',lambda m:'!'+str(int(m[1])+100),self.ir)
  self.assertEqual(entry_body(lower(changed)),re.sub(r'!(\d+)',lambda m:'!'+str(int(m[1])+100),entry_body(lower(self.ir))))
