"""Falsification controls for the receipt/oracle, without a Metal device."""
from pathlib import Path
import base64
import struct
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/tools'))
from verify_icb_texture import MODES, MASK, SENTINEL, reference, verify_execution


def fixture(folder,mode):
    cpu=mode.startswith('cpu');dispatch=not mode.endswith('_no_dispatch');runs=[]
    events=[]
    if cpu:
        events=[dict(operation='scope_install'),dict(operation='registered_manifest_library')]
        for _ in range(3):
            relocation=dict(function='sample_icb_arguments',library_SHA256='digest',binding_layout_v2=True,native_register_count=17,constant_buffer_valid_mask=7,parameters_offset=0,constant_buffer_bytes=512,bindings=[dict(index=i,offset=o)for i,o in enumerate([64,64,0])],native_literal_bank_0=dict(bytes=256,native_code_bytes=1216,variant_owner_retained=True))
            events.extend([dict(operation='materialize_CPU_command',command_bytes=464,user_kernel_invocations=0,relocation=relocation),dict(operation='initialize_resident_QMD'),dict(operation='prepare_resident_compute_commands',location=0,length=1,user_kernel_dispatches=0,GPU_initializers=1)])
            if dispatch:events.append(dict(operation='executeCommandsInBuffer',executed_indices=[0],concurrent_record_execution=False,evidence=dict(raw_packet_copies=1,sequence_elements=1,sequence_repetitions=1,command_bytes=464,native_preparation_GPU_dispatches=0,launches_suppressed=False,system_modified=False)))
        events.append(dict(operation='scope_restore',device_class_restored=True,system_modified=False))
    for trial,n in enumerate([16,65,257]):
        seed=0x125ab700+trial*97;native=struct.pack('<3Q',7,11,0x4000020);root=b'\xa5'*64+native+b'\xa5'*64
        length=(((n+31)//32)*32+8)*16;raw=bytearray(struct.pack('<I',SENTINEL)*(length//4))
        raw[64:64+n*16]=struct.pack('<'+'I'*n*4,*reference(trial,n,mode))
        params=struct.pack('<4I',n,seed,trial,0)+b'\xa5'*496
        payloads=dict(output=raw,root=root,**{'private-root':root,'parameters':params})
        for bank in range(2):
            words=[(((i*747796405+seed)&MASK)^0x12345678^(0x2468ace1 if bank else 0))for i in range(n+32)]
            payloads['input-'+str(bank)]=struct.pack('<'+'I'*len(words),*words)
        for suffix,data in payloads.items():(folder/f'trial-{trial}.{suffix}.bin').write_bytes(data)
        runs.append(dict(trial=trial,threads=n,seed=seed,texture=int(mode.endswith('_wrong_texture')),sampler=int(mode.endswith('_wrong_sampler')),input=int(mode.endswith('_wrong_buffer')),mismatches=0,output_guard_mismatches=0,root_guard_mismatches=0,command_status=4,native_bytes_base64=base64.b64encode(native).decode(),encoded_bytes_base64=base64.b64encode(native).decode(),texture_ID=7,sampler_ID=11,input_GPU_address_plus_offset=0x4000020))
    return dict(mode=mode,status='PASS',native_shader=True,CPU_ICB=cpu,interposition=cpu,performance_benchmark=False,argument_layout=[dict(offset=o)for o in [0,8,16]],user_dispatches=3 if dispatch else 0,runs=runs,scope_events=events,library_SHA256='digest')


class ICBTextureReceipts(unittest.TestCase):
    def test_all_positive_and_counterfactual_modes(self):
        with tempfile.TemporaryDirectory()as path:
            root=Path(path)
            for mode in MODES:
                p=root/mode;p.mkdir();r=verify_execution(fixture(p,mode),p)
                self.assertEqual(r['checked_uint32'],1352)
                self.assertFalse(r['new_runtime_resource_lifetime_support'])

    def check_corrupt(self,suffix,offset):
        with tempfile.TemporaryDirectory()as path:
            p=Path(path);d=fixture(p,'cpu');f=p/('trial-1.'+suffix+'.bin');b=bytearray(f.read_bytes());b[offset]^=1;f.write_bytes(b)
            with self.assertRaises(AssertionError):verify_execution(d,p)

    def test_false_success_does_not_hide_wrong_pixels(self):self.check_corrupt('output',64)
    def test_all_padding_is_checked(self):self.check_corrupt('output',-1)
    def test_private_argument_buffer_is_read_back(self):self.check_corrupt('private-root',64)
    def test_constants_are_unchanged(self):self.check_corrupt('parameters',-1)
    def test_nested_input_is_unchanged(self):self.check_corrupt('input-1',-1)

    def test_cpu_trace_cannot_claim_direct_or_suppressed_execution(self):
        for change in ['direct','suppressed','wrong_register_count','missing_restore']:
            with tempfile.TemporaryDirectory()as path:
                p=Path(path);d=fixture(p,'cpu')
                if change=='direct':d['interposition']=False
                elif change=='suppressed':next(e for e in d['scope_events']if e['operation']=='executeCommandsInBuffer')['evidence']['launches_suppressed']=True
                elif change=='wrong_register_count':next(e for e in d['scope_events']if e['operation']=='materialize_CPU_command')['relocation']['native_register_count']=8
                else:d['scope_events']=d['scope_events'][:-1]
                with self.assertRaises(AssertionError):verify_execution(d,p)

    def test_no_dispatch_witness_cannot_be_counted_as_gpu_computation(self):
        with tempfile.TemporaryDirectory()as path:
            p=Path(path);d=fixture(p,'cpu_no_dispatch');d['user_dispatches']=3
            with self.assertRaises(AssertionError):verify_execution(d,p)


if __name__=='__main__':unittest.main()
