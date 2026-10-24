"""Corrupt readback evidence offline; never submit malformed data to a GPU."""
from pathlib import Path
import base64
import struct
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/tools'))
from verify_gpu_icb_texture_rows import MODES,MASK,SENTINEL,reference,verify_rows,verify_trace


def trace_fixture():
    schema=dict(encoded_length=40,alignment=8,buffer_index=0,binding_count=3,members=[dict(index=i,offset=i*8,type=t)for i,t in enumerate([60,85,60,60,60])])
    events=[dict(operation=o)for o in ['register_native_source_IRv2_library','automatic_IRv2_library','automatic_IRv2_function']]
    events.append(dict(operation='register_native_IRv2_function',schema=schema,native_shader_compilation_replaced=False,native_reflection_reused=True,library_SHA256='digest',function='encode_image_command'))
    for _ in range(3):events.append(dict(operation='executeCommandsInBuffer',resident_GPU_descriptor=True,executed_indices=[1],evidence=dict(operation='resident_QMD_launch',resident_launches=1,launch_suppressed=False,CPU_QMD_uploads_in_launch=0,CPU_constant_uploads_in_launch=0,native_preparation_GPU_dispatches=0,primer_comparison=dict(exact_bytes=True,inactive_CB0_descriptor_normalized=False),system_modified=False,owner_original_profiles=[dict(original_record_function='sample_icb_arguments',native_register_count=17,constant_buffer_valid_mask=7,native_literal_bank_0=dict(bytes=256,native_code_bytes=1216,variant_owner_retained=True))])))
    events.append(dict(operation='scope_restore',device_class_restored=True,system_modified=False))
    plan=[dict(operation='encode_public_IRv2_arguments',bytes=40,native_Apple_ICB_identity=False),dict(operation='GPU_command_IR_materialization',record_CPU_read=False,rows=1),dict(operation='GPU_command_descriptor_selection',producer_encoded=True,CPU_shadow_is_execution_source=False,descriptor_CPU_upload=False,GPU_generated_resource_bindings=True,choice_CPU_read=False,candidate_count=1)]
    return dict(mode='gpu',status='PASS',native_shader=True,performance_benchmark=False,producer_library_SHA256='digest',scope_events=events,native_library_factories=True,manual_function_registrations=0,native_argument_encoder_restored=True,runs=[dict(plan_events=plan)for _ in range(3)])


def fixture(folder,mode):
    runs=[]
    for trial,n in enumerate([16,65,257]):
        seed=0x125ab700+trial*97;bank=(n^seed^trial)&1;producer=mode!='gpu_no_producer';groups=(n+31)//32
        roots=[0x400040,0x500040];out=0x600040;params_addr=0x700000;context_addr=0x800000;records_addr=0x900040;identity=0x4b50535000000001
        row=dict(trial=trial,threads=n,seed=seed,expected_GPU_bank=bank,mismatches=0,output_guard_mismatches=0,root_guard_mismatches=0,command_status=4,argument_root_GPU_addresses_plus_offsets=roots,output_GPU_address_plus_offset=out,parameters_GPU_address=params_addr,context_GPU_address=context_addr,records_GPU_address_plus_offset=records_addr)
        for key,suffix in [('texture','texture'),('sampler','sampler'),('input','buffer')]:row[key]=int(mode=='gpu_wrong_'+suffix)
        size=(((n+31)//32)*32+8)*16;raw=bytearray(struct.pack('<I',SENTINEL)*(size//4));raw[64:64+n*16]=struct.pack('<'+'I'*n*4,*reference(trial,n,mode));payloads={'output':raw}
        for which,(root_name,private_name)in enumerate([('root','private-root'),('alternate-root','alternate-private-root')]):
            prefix='alternate_'if which else'';native=struct.pack('<3Q',7+which,11+which,0x1000020+which*4096)
            row.update({prefix+'native_bytes_base64':base64.b64encode(native).decode(),prefix+'texture_ID':7+which,prefix+'sampler_ID':11+which,prefix+'input_GPU_address_plus_offset':0x1000020+which*4096})
            if not which:row['encoded_bytes_base64']=row['native_bytes_base64']
            payloads[root_name]=payloads[private_name]=b'\xa5'*64+native+b'\xa5'*64
            values=[(((i*747796405+seed)&MASK)^0x12345678^(0x2468ace1 if which else 0))for i in range(n+32)]
            payloads['input-'+str(which)]=struct.pack('<'+'I'*len(values),*values)
        payloads['parameters']=struct.pack('<4IQ',n,seed,trial,0,roots[1])+b'\xa5'*488
        payloads['producer-root']=b'\xa5'*64+struct.pack('<5Q',context_addr,identity,roots[0],out,params_addr)+b'\xa5'*64
        payloads['context']=struct.pack('<4IQ2I2Q10I',0x4b505343,3,1,3,records_addr,128,1,identity,params_addr,groups,1,1,32,1,1,0,2,0,0)+bytes(392)
        record=[0]*32
        if producer:
            record[:12]=[0x4b504952,115,0,0x4b504950,groups,1,1,0,32,1,1,0]
            for index,value in [(12,roots[bank]),(14,out),(16,params_addr)]:record[index:index+2]=[value&MASK,value>>32]
        payloads['records']=b'\xa5'*64+struct.pack('<32I',*record)+b'\xa5'*64
        actual_groups=groups if producer else 0
        payloads['witness']=b'\xa5'*64+struct.pack('<16I',actual_groups,1,1,0,32,1,1,bank if producer else 0,1 if producer else 2,0x4b504952,2,2,0,0,0,0x4b50524d)+b'\xa5'*64
        payloads['counts']=b'\xa5'*64+struct.pack('<2I',0,64)+b'\xa5'*64
        native=bytearray(65536);qmd=bytearray(4096)
        if producer:
            for offset,value in [(8,roots[bank]),(40,out),(72,params_addr)]:struct.pack_into('<Q',native,offset,value)
        for offset,value in zip([0x720,0x724,0x728,0x740,0x744,0x748],[actual_groups*32,1,1,actual_groups,1,1]):struct.pack_into('<I',native,offset,value)
        for offset,value in [(0x30,actual_groups),(0xb8,17<<24),(0x50,7)]:struct.pack_into('<I',qmd,offset,value)
        payloads['CB1']=native;payloads['QMD']=qmd
        for suffix,raw in payloads.items():(folder/f'trial-{trial}.{suffix}.bin').write_bytes(raw)
        runs.append(row)
    return dict(mode=mode,runs=runs,argument_layout=[dict(offset=o)for o in [0,8,16]])


class GPUTextureEvidence(unittest.TestCase):
    def test_all_modes_and_gpu_choice(self):
        with tempfile.TemporaryDirectory()as path:
            root=Path(path)
            for mode in MODES:
                p=root/mode;p.mkdir();proof=verify_rows(fixture(p,mode),p)
                self.assertEqual(proof['selected_banks'],[0,1,1]);self.assertEqual(proof['guard_bytes'],6168)
                self.assertEqual(proof['zero_CTA_records'],3 if mode=='gpu_no_producer'else 0)

    def corrupt(self,suffix,offset,mode='gpu'):
        with tempfile.TemporaryDirectory()as path:
            p=Path(path);d=fixture(p,mode);f=p/('trial-1.'+suffix+'.bin');raw=bytearray(f.read_bytes());raw[offset]^=1;f.write_bytes(raw)
            with self.assertRaises(AssertionError):verify_rows(d,p)

    def test_output_pass_counter_cannot_hide_wrong_sample(self):self.corrupt('output',64)
    def test_alternate_private_argument_buffer_is_checked(self):self.corrupt('alternate-private-root',64)
    def test_command_record_selected_address_is_checked(self):self.corrupt('records',64+48)
    def test_materialized_native_binding_is_checked(self):self.corrupt('CB1',8)
    def test_witness_resource_bank_is_checked(self):self.corrupt('witness',64+28)
    def test_materializer_atomic_count_is_checked(self):self.corrupt('counts',68)
    def test_allocation_guards_are_checked(self):self.corrupt('records',255)
    def test_absent_producer_requires_zero_cta_descriptor(self):self.corrupt('QMD',0x30,'gpu_no_producer')
    def test_cpu_resolved_root_cannot_be_claimed_as_gpu_choice(self):
        with tempfile.TemporaryDirectory()as path:
            p=Path(path);d=fixture(p,'gpu');f=p/'trial-1.producer-root.bin';raw=bytearray(f.read_bytes())
            struct.pack_into('<Q',raw,64+16,d['runs'][1]['argument_root_GPU_addresses_plus_offsets'][1]);f.write_bytes(raw)
            with self.assertRaises(AssertionError):verify_rows(d,p)
    def test_context_contract_is_checked(self):self.corrupt('context',0)

    def test_native_factory_trace_and_three_buffer_schema(self):
        d=trace_fixture();verify_trace(d)
        next(e for e in d['scope_events']if e['operation']=='register_native_IRv2_function')['schema']['binding_count']=4
        with self.assertRaises(AssertionError):verify_trace(d)

    def test_cpu_qmd_upload_cannot_be_called_gpu_materialization(self):
        d=trace_fixture();next(e for e in d['scope_events']if e['operation']=='executeCommandsInBuffer')['evidence']['CPU_QMD_uploads_in_launch']=1
        with self.assertRaises(AssertionError):verify_trace(d)

    def test_cpu_shadow_or_missing_materializer_is_rejected(self):
        for missing in [False,True]:
            d=trace_fixture()
            if missing:d['runs'][0]['plan_events']=[e for e in d['runs'][0]['plan_events']if e['operation']!='GPU_command_IR_materialization']
            else:d['runs'][0]['plan_events'][-1]['CPU_shadow_is_execution_source']=True
            with self.assertRaises(AssertionError):verify_trace(d)

    def test_native_getter_and_factory_restoration_are_required(self):
        d=trace_fixture();d['native_argument_encoder_restored']=False
        with self.assertRaises(AssertionError):verify_trace(d)
        d=trace_fixture();d['scope_events']=[e for e in d['scope_events']if e['operation']!='automatic_IRv2_function']
        with self.assertRaises(AssertionError):verify_trace(d)


if __name__=='__main__':unittest.main()
