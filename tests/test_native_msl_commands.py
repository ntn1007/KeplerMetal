"""CPU-only ABI transformation and raw-record verifier controls."""
from pathlib import Path
import hashlib
import json
import struct
import sys
import tempfile
import unittest
TOOLS=Path(__file__).resolve().parents[1]/'bridge/tools';sys.path.insert(0,str(TOOLS))
from public_native_msl_commands import msl_abi,lower_readonly_members
from verify_native_msl_records import expected,verify,MAGIC,ERROR


class NativeMSLCommandTests(unittest.TestCase):
    def test_readonly_lowering_is_member_scoped(self):
        text='struct A {\n constant uint *parameters [[id(4)]];\n};\nconstant uint table[2]={1,2};\nkernel void f(constant uint &value [[buffer(1)]]) {}\n'
        changed=lower_readonly_members(text,{'parameters':('uint',4)})
        self.assertIn('device const uint *parameters [[id(4)]];',changed)
        self.assertIn('constant uint table[2]',changed);self.assertIn('constant uint &value',changed)
        with self.assertRaises(AssertionError):lower_readonly_members(text,{'parameters':('float',4)})
        with self.assertRaises(AssertionError):lower_readonly_members(text,{'parameters':('uint',3)})

    def test_abi_transform_preserves_every_other_byte(self):
        text=(TOOLS.parent/'src/KeplerCommandIR.h').read_text();changed=msl_abi(text)
        self.assertEqual(changed.replace('typedef unsigned int uint32_t;\ntypedef unsigned long uint64_t;','#include <stdint.h>'),text)
        with self.assertRaises(AssertionError):msl_abi(text.replace('KP_COMMAND_RECORD_BYTES 128u','KP_COMMAND_RECORD_BYTES 256u'))
        with self.assertRaises(AssertionError):msl_abi(text.replace('#include <stdint.h>',''))

    def test_reset_copy_and_boundaries(self):
        args=(0x4b50495000000001,0x100040,0x200020)
        reset,_=expected(0,*args);self.assertEqual(reset[256:384],struct.pack('<I',MAGIC)+bytes(124))
        copied,_=expected(3,*args);self.assertEqual(copied[256:384],reset[256:384])
        self.assertEqual(struct.unpack_from('<IQ',copied,384+4),(9,args[0]))
        for operation in [12,13,14,15,16,20]:self.assertEqual(expected(operation,*args),(bytes([0xa5])*1792,)*2)

    def test_error_codes_and_stage_fields(self):
        args=(0x4b50495000000001,0x100040,0x200020)
        for operation,code in [(5,4),(6,1),(7,1),(8,2),(9,3),(10,5),(11,5),(18,1),(19,2),(21,1)]:
            a,b=expected(operation,*args);row=1 if operation in [10,11]else 0
            self.assertEqual(struct.unpack_from('<I',a,256+row*128+76)[0],code)
            self.assertTrue(struct.unpack_from('<I',a,256+row*128+4)[0]&ERROR)
        a,_=expected(17,*args);self.assertEqual(struct.unpack_from('<6I',a,256+80),(1,2,3,4,5,6))

    def fixture(self,root,dispatch=True):
        (root/'outputs').mkdir();(root/'execution').mkdir();(root/'application').write_bytes(b'offline CPU fixture, never executed')
        digest=hashlib.sha256((root/'application').read_bytes()).hexdigest()
        (root/'inputs.json').write_text(json.dumps(dict(executable_SHA256=digest)))
        (root/'execution/manifest.json').write_text(json.dumps(dict(exit_code=0,SIGKILL_requested=False,authoritative_ps_status='',GPU_reservation=dict(state='terminal'),original_binary_sha256=digest)))
        name='NVIDIA GeForce GTX 880M';result=dict(device=name,registry_id=1,
            device_identity=dict(schema=1,name=name,registry_id=1,PCI_registry_id=2,PCI_vendor_id=0x10de,PCI_device_id=0x1198),
            producer_backend='native_msl',record_execution=False,instruction_import=False,performance_benchmark=False,
            mode='execute'if dispatch else'no_dispatch',user_dispatches=23 if dispatch else 0,command_buffers=23,cases=[])
        for operation in range(23):
            row=dict(operation=operation,command_status=4,contexts_unchanged=True,pipeline_token=0x4b50495000000001,storage_address=0x100040,constant_address=0x200020)
            result['cases'].append(row)
            for k,data in enumerate(expected(operation,row['pipeline_token'],row['storage_address'],row['constant_address'],dispatch)):
                (root/'outputs'/f'case-{operation}-records-{k}.bin').write_bytes(data)
        (root/'results.json').write_text(json.dumps(result))

    def test_full_record_and_no_dispatch_oracles(self):
        for dispatch in [False,True]:
            with tempfile.TemporaryDirectory()as folder:
                root=Path(folder);self.fixture(root,dispatch);proof=verify(root)
                self.assertEqual(proof['cases'],23);self.assertEqual(proof['user_dispatches'],23 if dispatch else 0)

    def test_reported_success_cannot_mask_data_or_guard_change(self):
        for offset in [0,256,1791]:
            with tempfile.TemporaryDirectory()as folder:
                root=Path(folder);self.fixture(root);p=root/'outputs/case-0-records-0.bin';data=bytearray(p.read_bytes());data[offset]^=1;p.write_bytes(data)
                with self.assertRaises(AssertionError):verify(root)


if __name__=='__main__':unittest.main()
