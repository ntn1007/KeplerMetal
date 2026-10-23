"""Portable resource-result tests; fixtures below never execute on a GPU."""
from pathlib import Path
import base64
import copy
import importlib.util
import struct
import sys
import tempfile
import unittest

TOOLS=Path(__file__).resolve().parents[1]/'bridge/tools';sys.path.insert(0,str(TOOLS))
spec=importlib.util.spec_from_file_location('identity_oracle',TOOLS/'verify_native_resource_identity.py')
oracle=importlib.util.module_from_spec(spec);spec.loader.exec_module(oracle)
NAME='NVIDIA GeForce GTX 880M'
IDENTITY=dict(device=NAME,registry_id=1,device_identity=dict(schema=1,name=NAME,registry_id=1,
    PCI_registry_id=2,PCI_vendor_id=0x10de,PCI_device_id=0x1198))


class NativeResourceIdentityTests(unittest.TestCase):
    def fixture(self,root,mode='direct'):
        result=dict(copy.deepcopy(IDENTITY),mode=mode,status='PASS',native_shader=True,interposition=False,
            user_dispatches=0 if mode=='no_dispatch'else 3,argument_layout=[dict(offset=o)for o in [0,8,16]],runs=[])
        for trial,count in enumerate([16,65,257]):
            native=struct.pack('<6I',3,1,0x100000,0xa5a5a5a5,0x10020,0)
            encoded=native if mode=='native'else struct.pack('<3Q',3,0x100000,0x10020)
            guard=struct.pack('<I',oracle.SENTINEL)*16
            values=oracle.reference(trial,count,mode)
            (root/f'trial-{trial}.output.bin').write_bytes(guard+struct.pack('<'+'I'*len(values),*values)+guard)
            (root/f'trial-{trial}.root.bin').write_bytes(bytes([0xa5])*64+encoded+bytes([0xa5])*64)
            result['runs'].append(dict(trial=trial,threads=count,seed=0x125ab700+trial*97,
                texture=int(mode=='wrong_texture'),sampler=int(mode=='wrong_sampler'),input=int(mode=='wrong_buffer'),
                mismatches=0,output_guard_mismatches=0,root_guard_mismatches=0,command_status=4,
                encoded_bytes_base64=base64.b64encode(encoded).decode(),native_bytes_base64=base64.b64encode(native).decode(),
                texture_ID=3,sampler_ID=0x100000,input_GPU_address_plus_offset=0x10020))
        return result

    def test_modes_are_discriminating(self):
        for trial,count in enumerate([16,65,257]):
            baseline=oracle.reference(trial,count,'native')
            self.assertEqual(baseline,oracle.reference(trial,count,'direct'))
            for mode in ['wrong_texture','wrong_sampler','wrong_buffer','no_dispatch']:
                self.assertNotEqual(baseline,oracle.reference(trial,count,mode))

    def test_positive_and_expected_difference_modes(self):
        for mode in oracle.MODES:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory()as tmp:
                root=Path(tmp);r=self.fixture(root,mode);p=oracle.execute(r,root)
                self.assertEqual(p['checked_uint32'],1352)
                self.assertEqual(p['expected_differences_from_baseline']>0,mode not in ['native','direct'])

    def test_cpu_report_cannot_hide_corrupted_output(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);r=self.fixture(root);p=root/'trial-1.output.bin';raw=bytearray(p.read_bytes());raw[64]^=1;p.write_bytes(raw)
            with self.assertRaises(AssertionError):oracle.execute(r,root)

    def test_root_and_output_guards_checked_from_raw_files(self):
        for suffix in ['output','root']:
            with tempfile.TemporaryDirectory()as tmp:
                root=Path(tmp);r=self.fixture(root);p=root/f'trial-0.{suffix}.bin';raw=bytearray(p.read_bytes());raw[-1]^=1;p.write_bytes(raw)
                with self.assertRaises(AssertionError):oracle.execute(r,root)

    def test_changed_view_identity_is_not_masked(self):
        with tempfile.TemporaryDirectory()as tmp:
            root=Path(tmp);r=self.fixture(root);r['runs'][0]['texture_ID']=4
            with self.assertRaises(AssertionError):oracle.execute(r,root)

    def test_specific_icb_compiler_refusal(self):
        r=dict(copy.deepcopy(IDENTITY),library_loaded=True,function_created=True,interposition=False,
            GPU_dispatches=0,GPU_command_buffers=0,function_encoder_created=True,encoded_length=0,
            pipeline_created=False,outcome='PIPELINE_REFUSED',
            pipeline_error='CompilerError: Unsupported indirect argument kind "air.command_buffer"')
        self.assertEqual(oracle.icb_compile(r)['status'],'PASS_EXPECTED_COMPILER_REFUSAL')
        for key,value in [('pipeline_created',True),('pipeline_error','File not found'),('encoded_length',8)]:
            bad=dict(r);bad[key]=value
            with self.assertRaises(AssertionError):oracle.icb_compile(bad)


if __name__=='__main__':unittest.main()
