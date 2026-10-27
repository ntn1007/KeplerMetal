# SPDX-License-Identifier: MIT
import json
from pathlib import Path
import re
import struct
import sys
import unittest
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'bridge/tools'))
from air_indexed_render_lowering import lower,INDEXED
from air_reset_lowering import entry_body
from verify_indexed_render import transform,why,draw_parameters,extra_buffers
from verify_render_state_catalogue import source_record


class IndexedDrawTranslation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.ir=json.loads((ROOT/'tests/fixtures/air_indexed_render_ir.json').read_text())['IR']

    def test_both_pointer_widths_preserve_entry_and_order(self):
        expected=entry_body(self.ir).replace('@air.reset_render_command','@kp_reset_render_command')
        for bits,name in INDEXED.items():expected=expected.replace('@'+name,f'@kp_indexed_render_{bits}')
        self.assertEqual(entry_body(lower(self.ir)),expected)

    def test_ordinary_index_buffer_metadata_preserved(self):
        for line in self.ir.splitlines():
            if '!"air.arg_name", !"index16"'in line or '!"air.arg_name", !"index32"'in line:self.assertIn(line,lower(self.ir))

    def test_metadata_renumbering(self):
        changed=re.sub(r'!(\d+)',lambda m:'!'+str(int(m[1])+300),self.ir)
        self.assertEqual(entry_body(lower(changed)),re.sub(r'!(\d+)',lambda m:'!'+str(int(m[1])+300),entry_body(lower(self.ir))))

    def test_constant_address_space_refused(self):
        with self.assertRaises(ValueError):lower(self.ir.replace('p1i16','p2i16').replace('i16 addrspace(1)*','i16 addrspace(2)*'))

    def test_wrong_primitive_refused(self):
        line=next(l for l in self.ir.splitlines()if'call void @'+INDEXED[16]in l)
        with self.assertRaises(ValueError):lower(self.ir.replace(line,line.replace(', i32 3,',', i32 1,',1)))

    def test_pointer_declaration_mismatch_refused(self):
        line=next(l for l in self.ir.splitlines()if l.startswith('declare void @'+INDEXED[16]))
        with self.assertRaises(ValueError):lower(self.ir.replace(line,line.replace('i16 addrspace(1)*','i32 addrspace(1)*')))

    def test_unimplemented_resource_setters_refused(self):
        with self.assertRaises(ValueError):lower(self.ir+'declare void @air.set_vertex_buffer_render_command()\n')

    def test_index_helpers_do_not_load_from_provided_pointer(self):
        text=lower(self.ir)
        self.assertIn('ptrtoint i16 addrspace(1)* %indices to i64',text)
        self.assertIn('ptrtoint i32 addrspace(1)* %indices to i64',text)
        self.assertNotRegex(text,r'load .*\* %indices,')


class IndexedDrawOracle(unittest.TestCase):
    ids=[0x4b50535200000003,0x4b50535200000004]
    foreign=[0x4b50535200000001,0x4b50535200000002]
    def record(self,mode,t,slot):
        raw=source_record(t,slot,'gpu',self.ids,self.foreign)
        return struct.unpack('<8IQ6I',transform(mode,t,slot,raw,self.ids))

    def test_signed_base_vertex_and_index_types(self):
        a,b=(self.record('indexed_gpu',0,s)for s in(1,3))
        self.assertEqual(a[1:7],(1,3,1,0,2,1));self.assertEqual(b[1:7],(2,3,1,3,0xfffffffe,2))

    def test_complete_indexed_rectangle(self):
        self.assertEqual(draw_parameters(1,3),(0,6,1));self.assertEqual(draw_parameters(2,1),(0,6,1))

    def test_count_span_rejection(self):
        for slot in(1,3):
            r=self.record('indexed_gpu',3,slot);records=[None]*4;records[slot]=r
            self.assertEqual(why('indexed_gpu',3,slot,self.ids.index(r[8]),0,records,self.ids,'gpu'),3)

    def test_reset_keeps_geometry_inert_without_state(self):
        r=self.record('indexed_after_reset',0,1);self.assertEqual(r[0],0x4b505353);self.assertEqual(r[8],0)
        self.assertEqual(self.record('indexed_then_reset',0,1),(0,)*15)

    def test_last_draw_replaces_invalid_parameters(self):
        for slot in(1,3):
            self.assertGreater(self.record('indexed_gpu',5,slot)[2],6)
            r=self.record('indexed_last',5,slot);self.assertEqual(r[2],3);self.assertEqual(r[3],1)

    def test_unknown_identity_is_not_silently_reassigned(self):
        self.assertEqual(self.record('indexed_gpu',2,3),(0,)*15)
        last=self.record('indexed_last',2,3);self.assertEqual(last[0],0x4b505353);self.assertEqual(last[8],0)

    def test_foreign_pointer_wrong_kind_missing_table_clear(self):
        for mode in ['indexed_foreign','indexed_wrong_kind','indexed_missing_table']:
            for slot in(1,3):self.assertEqual(self.record(mode,0,slot),(0,)*15)

    def test_nonindexed_slot_and_missing_dispatch_unchanged(self):
        for t in range(8):
            for s in range(4):
                raw=source_record(t,s,'gpu',self.ids,self.foreign)
                self.assertEqual(transform('indexed_no_dispatch',t,s,raw,self.ids),raw)
                if s not in(1,3):self.assertEqual(transform('indexed_gpu',t,s,raw,self.ids),raw)

    def test_prefix_and_inline_table_layout(self):
        row=dict(trial=0,identifiers=self.ids,root_context_alive_before_commit=True,argument_encoder_released_before_commit=True,root_function_restored_before_commit=True,
         AIR_reset=dict(capacity=4,count=4,seed=80,mask=0,target_slot=1,order=0,dispatched=True,public_getter='function',encoded_length=8,alignment=8,reflection_requested=False,reflection_type=0,client_GPU_address_construction=False,root_refusals=[],
          context_storage_mode=2,records_storage_mode=2,root_storage_mode=0,indices_storage_mode=2,output_storage_mode=2,index_storage_modes=[2,2],index_binding_count=4,index_binding_table_offset=128,
          context_GPU_address=0x10040,records_GPU_address=0x20040,root_GPU_address=0x30040,index_buffer_GPU_addresses=[0x40040,0x50040],index_input_GPU_addresses=[0x40040,0x50040]))
        ctx=extra_buffers(row,'indexed_gpu')['reset-context'];self.assertEqual(len(ctx),384)
        self.assertEqual(struct.unpack_from('<4I2Q',ctx,64),(0x4b505243,1,4,64,0x20040,0))
        self.assertEqual(struct.unpack_from('<4I2Q',ctx,96),(0x4b504958,1,4,48,0x10080,0))
        self.assertEqual(struct.unpack_from('<3Q4IQ',ctx,128),(self.ids[0],0x40040,12,1,1,6,0,0))
        self.assertEqual(struct.unpack_from('<3Q4IQ',ctx,272),(self.ids[1],0x50040,24,3,2,6,0,0))
        self.assertEqual(ctx[:64]+ctx[-64:],b'\xa5'*128)


if __name__=='__main__':unittest.main()
