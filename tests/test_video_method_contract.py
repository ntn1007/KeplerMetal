# SPDX-License-Identifier: MIT
"""Synthetic descriptor controls; no Mach-O or hardware execution."""
import json,struct,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/tools'))
import video_method_contract as tool

class VideoMethodDescriptorTests(unittest.TestCase):
    def setUp(self):
        self.address=0x1000
        self.expected=('method',0x7144,3,8,0xffffffff)
        self.symbols=[{'name':'method','type':0x0e,'value':0x7144}]
        self.raw=struct.pack('<QQQI4xQQ',0,0x7144,0,3,8,0xffffffff)
    def check(self,raw=None,relocs=None,symbols=None):
        with patch.object(tool,'file_bytes',return_value=(0x100,self.raw if raw is None else raw)):
            return tool.descriptor(b'',self.address,self.expected,relocs or {},self.symbols if symbols is None else symbols)
    def test_valid_variable_output(self):
        r=self.check();self.assertEqual(r['count0'],8);self.assertEqual(r['count1'],0xffffffff);self.assertEqual(r['member_pointer_kind'],'direct')
    def test_changed_structure_size_refused(self):
        bad=struct.pack('<QQQI4xQQ',0,0x7144,0,3,7,0xffffffff)
        with self.assertRaisesRegex(ValueError,'descriptor differs'):self.check(raw=bad)
    def test_invalid_pointer_adjustment_refused(self):
        bad=struct.pack('<QQQI4xQQ',0,0x7144,1,3,8,0xffffffff)
        with self.assertRaisesRegex(ValueError,'descriptor differs'):self.check(raw=bad)
    def test_external_relocation_refused(self):
        with self.assertRaisesRegex(ValueError,'relocation'):self.check(relocs={self.address+8:[{}]})
    def test_symbol_mismatch_refused(self):
        with self.assertRaisesRegex(ValueError,'Missing/ambiguous'):self.check(symbols=[])
    def test_static_evidence_bound_must_match_exact_observation(self):
        evidence={'operation':'analyze_function','subject':{'digest':{'sha256':tool.IO_SHA}},
          'evidence_id':'ev_9ef4aee42a6f2eee153d0e5ff80c39bb8a4771f391d11562decd68341dbbbd03',
          'provider':{'id':'ghidra','name':'Ghidra','version':'12.1.4'},
          'analysis_profile':{'digest':'c027fac311b23874c52441ed55610273dff33987b0370a0589c90be8f6d72b7a'},
          'normalized_result':{'procedure':{'address':'0x7144','body':{'total_bytes':331}},
           'assembly':['0x7166: CMP RCX, 0x8','0x716a: JC 0x0000727d',
             '0x7173: CMP qword ptr [R8], 0x30','0x7177: JC 0x0000727d',
             '0x71fe: CALL qword ptr [RAX + 0xa68]']}}
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'evidence.json';path.write_text(json.dumps(evidence))
            with patch.object(tool,'GET_DATA_REA_SHA',tool.sha(path.read_bytes())):
                self.assertEqual(tool.get_data_evidence(path)['output_capacity_minimum_in_body'],48)
            evidence['normalized_result']['assembly'][2]='0x7173: CMP qword ptr [R8], 0x20'
            path.write_text(json.dumps(evidence))
            with patch.object(tool,'GET_DATA_REA_SHA',tool.sha(path.read_bytes())):
                with self.assertRaisesRegex(ValueError,'Bounds/indirect-call'):tool.get_data_evidence(path)

    def test_allocator_evidence_requires_class_and_size_reads(self):
        evidence={'operation':'analyze_function','subject':{'digest':{'sha256':tool.IO_SHA}},
          'evidence_id':'ev_73185ac90e6c691e4d2eca5f95e61e33d6f341b329cd17b6934db77cab79f6b9',
          'provider':{'id':'ghidra','name':'Ghidra','version':'12.1.4'},
          'analysis_profile':{'digest':'c027fac311b23874c52441ed55610273dff33987b0370a0589c90be8f6d72b7a'},
          'normalized_result':{'procedure':{'address':'0x9f70','body':{'total_bytes':2532}},
           'assembly':['0x9f84: MOV R9D, dword ptr [RSI]',
             '0x9fa1: CMP R9D, dword ptr [RDI + 0x6dc]',
             '0x9fa8: JNC 0x0000a0c0','0x9fe5: MOV EAX, dword ptr [RSI + 0x4]',
             '0x9fff: CALL 0x00009ede','0xa3b1: CALL qword ptr [RAX + 0xa70]']}}
        with tempfile.TemporaryDirectory() as t:
            path=Path(t)/'evidence.json';path.write_text(json.dumps(evidence))
            with patch.object(tool,'GET_BUFFER_REA_SHA',tool.sha(path.read_bytes())):
                self.assertEqual(tool.get_buffer_evidence(path)['buffer_allocation_virtual_slot'],'0xa70')
            evidence['normalized_result']['assembly'][3]='0x9fe5: MOV EAX, dword ptr [RSI + 0x8]'
            path.write_text(json.dumps(evidence))
            with patch.object(tool,'GET_BUFFER_REA_SHA',tool.sha(path.read_bytes())):
                with self.assertRaisesRegex(ValueError,'Input/allocator'):tool.get_buffer_evidence(path)

    def test_all_ones_64bit_is_not_the_32bit_variable_sentinel(self):
        bad=struct.pack('<QQQI4xQQ',0,0x7144,0,3,8,0xffffffffffffffff)
        with self.assertRaisesRegex(ValueError,'descriptor differs'):self.check(raw=bad)

if __name__=='__main__':unittest.main()
