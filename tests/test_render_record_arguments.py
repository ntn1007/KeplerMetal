# SPDX-License-Identifier: MIT
import copy
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/tools'))
from verify_render_record_arguments import argument_buffers,REFUSALS


def row(mode='arguments_gpu'):
    dispatch=not mode.startswith('arguments_no_reset')
    return dict(trial=0,root_context_alive_before_commit=True,argument_encoder_released_before_commit=True,
        root_function_restored_before_commit=True,AIR_reset=dict(dispatched=dispatch,capacity=4,count=4,seed=3,mask=0,target_slot=3,
        context_GPU_address=0x10040,records_GPU_address=0x20040,root_GPU_address=0x30040,
        context_storage_mode=2,records_storage_mode=2,root_storage_mode=0,indices_storage_mode=2,output_storage_mode=2,
        public_getter={'arguments_device':'device','arguments_reflection':'function_reflection'}.get(mode,'function'),
        encoded_length=8,alignment=8,reflection_requested=mode=='arguments_reflection',reflection_type=85 if mode=='arguments_reflection'else 0,
        root_refusals=list(REFUSALS)if mode=='arguments_contracts'else[],client_GPU_address_construction=False))


class RenderRecordArgumentEvidence(unittest.TestCase):
    def test_shared_root_points_to_owned_private_context(self):
        data=argument_buffers(row(),'arguments_gpu')
        self.assertEqual(struct.unpack_from('<Q',data['reset-root'],64),(0x10040,))
        self.assertEqual(struct.unpack_from('<4I2Q',data['reset-context'],64),(0x4b505243,1,4,64,0x20040,0))

    def test_public_getter_paths(self):
        for mode in ['arguments_gpu','arguments_device','arguments_reflection','arguments_arrays','arguments_reuse']:
            self.assertIn('reset-output',argument_buffers(row(mode),mode))

    def test_wrong_getter_cannot_claim_success(self):
        r=row();r['AIR_reset']['public_getter']='device'
        with self.assertRaises(AssertionError):argument_buffers(r,'arguments_gpu')

    def test_native_compiled_reflection_must_not_be_fabricated(self):
        r=row('arguments_reflection');r['AIR_reset']['reflection_type']=58
        with self.assertRaises(AssertionError):argument_buffers(r,'arguments_reflection')

    def test_context_or_encoder_lifetime_loss_refused(self):
        for field in ['root_context_alive_before_commit','argument_encoder_released_before_commit','root_function_restored_before_commit']:
            r=row();r[field]=False
            with self.assertRaises(AssertionError):argument_buffers(r,'arguments_gpu')

    def test_complete_refusal_ledger_required(self):
        r=row('arguments_contracts');self.assertEqual(len(REFUSALS),22)
        argument_buffers(r,'arguments_contracts');r['AIR_reset']['root_refusals'].pop()
        with self.assertRaises(AssertionError):argument_buffers(r,'arguments_contracts')

    def test_manual_address_construction_cannot_be_reported_as_encoder_path(self):
        r=row();r['AIR_reset']['client_GPU_address_construction']=True
        with self.assertRaises(AssertionError):argument_buffers(r,'arguments_gpu')

    def test_missing_dispatch_has_sentinel_witness(self):
        a=argument_buffers(row('arguments_no_reset'),'arguments_no_reset')
        b=argument_buffers(row(),'arguments_gpu')
        self.assertEqual(a['reset-output'],b'\xa5'*144);self.assertNotEqual(a['reset-output'],b['reset-output'])

    def test_rebinding_preserves_prior_exported_root(self):
        d=argument_buffers(row('arguments_reuse'),'arguments_reuse')
        self.assertEqual(d['reset-root'],d['reset-spare-root'])

    def test_wrong_root_shape_or_storage_refused(self):
        for field,value in [('encoded_length',16),('alignment',16),('root_storage_mode',2)]:
            r=row();r['AIR_reset'][field]=value
            with self.assertRaises(AssertionError):argument_buffers(r,'arguments_gpu')

if __name__=='__main__':unittest.main()
