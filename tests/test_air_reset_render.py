# SPDX-License-Identifier: MIT
from pathlib import Path
import copy
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/tools'))
from verify_air_reset_render import extra_buffers,reset_witness
from verify_render_state_catalogue import source_record,scene_buffers,reason
from verify_air_reset_dataflow import expected,CASES


def row():
    return {'AIR_reset':dict(dispatched=True,capacity=4,count=4,seed=3,mask=0,target_slot=3,
        context_GPU_address=0x10040,records_GPU_address=0x20040,root_GPU_address=0x30040,
        **{k:2 for k in ['context_storage_mode','records_storage_mode','root_storage_mode','indices_storage_mode','output_storage_mode']})}


class AIRRenderResetTests(unittest.TestCase):
    def test_reset_clears_only_target_record(self):
        ids=[0x4b50535200000003,0x4b50535200000004];foreign=[x+2 for x in ids]
        for trial in range(8):
            before=scene_buffers(trial,'gpu',ids,foreign);after=scene_buffers(trial,'gpu',ids,foreign,3)
            for name in before:
                if name!='records':self.assertEqual(before[name],after[name])
            self.assertEqual(after['records'][:256],before['records'][:256])
            self.assertEqual(after['records'][256:320],bytes(64));self.assertEqual(after['records'][320:],before['records'][320:])

    def test_cleared_defective_records_report_empty(self):
        self.assertEqual(reason(2,3,0,'gpu'),5)
        for trial in range(8):
            for state in range(2):self.assertEqual(reason(trial,3,state,'gpu',3),1)
            self.assertEqual(reason(trial,2,0,'gpu',3),4)

    def test_no_reset_default_unchanged(self):
        for trial in range(8):
            for slot in range(4):
                self.assertEqual(source_record(trial,slot,'gpu',[1,2],[3,4]),source_record(trial,slot,'gpu',[1,2],[3,4],None))

    def test_context_matches_qualified_shader_contract(self):
        extra=extra_buffers(row(),'air_gpu')
        self.assertEqual(struct.unpack_from('<4I2Q',extra['reset-context'],64),(0x4b505243,1,4,64,0x20040,0))
        self.assertEqual(struct.unpack_from('<Q',extra['reset-root'],64),(0x10040,))
        self.assertEqual(struct.unpack_from('<4I',extra['reset-indices'],64),(3,11,7,15))

    def test_witness_matches_preceding_producer_oracle(self):
        recipe=next(c for c in CASES if c[0]=='prefix');wanted,_=expected(recipe,True)
        self.assertEqual(extra_buffers(row(),'air_gpu')['reset-output'][64:80],wanted[1][64:80])

    def test_missing_dispatch_preserves_output(self):
        r=row();r['AIR_reset']['dispatched']=False
        self.assertEqual(extra_buffers(r,'air_no_reset')['reset-output'],b'\xa5'*144)

    def test_bad_context_preserves_arithmetic(self):
        normal=extra_buffers(row(),'air_gpu');bad=extra_buffers(row(),'air_bad_context')
        self.assertEqual(normal['reset-output'],bad['reset-output'])
        self.assertEqual(struct.unpack_from('<I',bad['reset-context'],64)[0],0x4b505242)

    def test_guard_regions(self):
        for data in extra_buffers(row(),'air_gpu').values():self.assertEqual(data[:64]+data[-64:],b'\xa5'*128)

    def test_address_alias_or_alignment_refused(self):
        for address in [0,1,0x20040,1<<40]:
            r=row();r['AIR_reset']['context_GPU_address']=address
            with self.assertRaises(AssertionError):extra_buffers(r,'air_gpu')

    def test_private_modes_observed(self):
        for field in ['context_storage_mode','records_storage_mode','root_storage_mode','indices_storage_mode','output_storage_mode']:
            r=row();r['AIR_reset'][field]=0
            with self.assertRaises(AssertionError):extra_buffers(r,'air_gpu')

    def test_missing_dispatch_cannot_be_claimed(self):
        with self.assertRaises(AssertionError):extra_buffers(row(),'air_no_reset')

if __name__=='__main__':unittest.main()
