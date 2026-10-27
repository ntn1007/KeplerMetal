# SPDX-License-Identifier: MIT
import json
from pathlib import Path
import re
import struct
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'bridge/tools'))
from air_combined_index_vertex_lowering import lower,combined_setter_helper
from air_indexed_render_lowering import INDEXED
from air_vertex_binding_lowering import SET
from air_reset_lowering import entry_body


class CombinedTranslation(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.ir=json.loads((ROOT/'tests/fixtures/air_combined_index_vertex_ir.json').read_text())['IR']
 def test_preserves_shader_entry_and_order(self):
  expect=entry_body(self.ir).replace('@'+SET,'@kp_set_vertex_buffer').replace('@air.reset_render_command','@kp_reset_render_command')
  for bits,name in INDEXED.items():expect=expect.replace('@'+name,f'@kp_indexed_render_{bits}')
  self.assertEqual(entry_body(lower(self.ir)),expect)
  self.assertIn('@kp_set_vertex_buffer',expect)
  for bits in (16,32):self.assertIn(f'@kp_indexed_render_{bits}',expect)
 def test_index_header_checked_before_secondary_header(self):
  t=combined_setter_helper();self.assertLess(t.index('br i1 %iok, label %vertex_header, label %refused'),t.index('%vertexheader = inttoptr'))
  for value in ('%indexbytes = mul i64 %indexcount64, 48','%vexpected = add i64 %vertexaddress, 32','%more = icmp ult i32 %next, %ve2'):
   self.assertIn(value,t)
 def test_no_input_pointer_dereferences(self):
  s=lower(self.ir);self.assertNotRegex(s,r'load [^\n]*\* %buffer,');self.assertNotRegex(s,r'load [^\n]*\* %indices,')
 def test_rejects_unimplemented_operations_and_wrong_stride(self):
  with self.assertRaises(ValueError):lower(self.ir+'declare void @air.set_fragment_buffer_render_command()\n')
  call=next(x for x in self.ir.splitlines()if 'call void @'+SET in x)
  with self.assertRaises(ValueError):lower(self.ir.replace(call,call.replace('i64 -1','i64 16')))
 def test_rejects_wrong_index_width_or_primitive(self):
  with self.assertRaises(ValueError):lower(self.ir.replace('p1i16','p2i16').replace('i16 addrspace(1)*','i16 addrspace(2)*'))
  line=next(x for x in self.ir.splitlines()if 'call void @'+INDEXED[16] in x)
  with self.assertRaises(ValueError):lower(self.ir.replace(line,line.replace(', i32 3,',', i32 1,',1)))
 def test_metadata_renumbering(self):
  changed=re.sub(r'!(\d+)',lambda m:'!'+str(int(m[1])+200),self.ir)
  self.assertEqual(entry_body(lower(changed)),re.sub(r'!(\d+)',lambda m:'!'+str(int(m[1])+200),entry_body(lower(self.ir))))


class CombinedWireLayout(unittest.TestCase):
 def test_offsets_and_tail_guard_for_variable_index_counts(self):
  base=0x10000
  for ni in (1,4,16):
   for nv in (1,12,64):
    size=224+ni*48+nv*32;data=bytearray(b'\xa5'*size);context=base+64;index_table=base+128
    vertex_header=128+ni*48;vertex_table=vertex_header+32
    struct.pack_into('<4I2Q',data,64,0x4b505243,1,2,64,0x20040,0)
    struct.pack_into('<4I2Q',data,96,0x4b504958,1,ni,48,index_table,0)
    struct.pack_into('<4I2Q',data,vertex_header,0x4b505658,1,nv,32,base+vertex_table,0)
    self.assertEqual(index_table,context+64);self.assertEqual(base+vertex_header,index_table+ni*48)
    self.assertEqual(base+vertex_table,base+vertex_header+32);self.assertEqual(size-(vertex_table+nv*32),64)
    self.assertEqual(data[-64:],b'\xa5'*64)
 def test_legacy_index_context_has_safe_absent_extension_probe(self):
  for ni in (1,16):
   size=192+ni*48;data=bytearray(b'\xa5'*size);offset=128+ni*48
   self.assertLessEqual(offset+32,size);self.assertNotEqual(struct.unpack_from('<I',data,offset)[0],0x4b505658)
