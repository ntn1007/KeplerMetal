"""Falsify captured evidence offline; fixtures never submit work to Metal."""
from pathlib import Path
import json
import struct
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/tools'))
from verify_render_state_catalogue import (verify_rows,scene_buffers,source_record,reason,choice,
    color,RECTS,values)


def fixture(root,mode='release'):
    root=Path(root);out=root/'outputs';out.mkdir();trials=1 if mode=='release'else 8
    native=mode.endswith('native');consumer=mode!='no_consumer';events=[];rows=[]
    for trial in range(trials):
        ids=[0x4b50535200000003+trial*4,0x4b50535200000004+trial*4]
        foreign=[i-2 for i in ids];payloads=scene_buffers(trial,mode,ids,foreign)
        for tokens in [foreign,ids]:events.append(dict(operation='create_render_state_catalogue',state_identifiers=tokens,logical_slots=4,states=2,native_slots=8,native_Apple_pipeline_resource_IDs=False))
        if not native:
            table=bytearray();args=bytearray(b'\xa5'*384);witness=bytearray(b'\xa5'*256)
            for slot in range(4):
                for state in range(2):
                    flat=slot*2+state
                    max_args=[[6,1,5,0,0],[6,1,0,2,1],[0]*5,[6,1,0,0xfffffffe,2]][slot]
                    table.extend(struct.pack('<8IQ6I',*max_args,[0,1,0,2][slot],int(slot!=2),0,ids[state],slot,0,0,0,0,0))
                    why=reason(trial,slot,state,mode);active=why==0 and trial!=7 and mode!='no_producer'
                    arguments=struct.unpack('<8IQ6I',source_record(trial,slot,mode,ids,foreign))[2:7]if active else[0]*5
                    struct.pack_into('<5I',args,64+flat*32,*arguments)
                    struct.pack_into('<4I',witness,64+flat*16,1,int(active),(slot<<16)|state,0x4b530000|why)
            payloads.update(templates=table,arguments=args,witness=witness)
            events.append(dict(operation='prepare_GPU_indirect_render_range',slots=4,native_slots=8,GPU_state_selection=True,GPU_generated_draw_records=True,range_CPU_read=False))
            if consumer:
                events.append(dict(operation='execute_GPU_indirect_render_range',slot_capacity=4,native_slot_capacity=8,state_count=2,GPU_state_selection=True,selection_CPU_read=False,record_CPU_read=False,range_CPU_read=False,state_selection_method='native_indirect_draw_predicates',caller_pipeline_restored=True,caller_vertex_slots_restored=2,caller_fragment_slots_restored=1,
                    evidence=dict(raw_record_copies=0,resource_leases_until_completion=True,draw_arguments_CPU_read=False,draw_calls=[dict(slot=s,kind=k,argument_offset=o)for s,k,o in [(0,0,64),(1,0,96),(2,1,128),(3,1,160),(6,2,256),(7,2,288)]])))
        from verify_render_state_catalogue import texel
        for bank in range(2):payloads[f'texture-{bank}']=struct.pack('<12288f',*[v for y in range(48)for x in range(64)for v in texel(bank,x,y)])
        pixels=[];v=values(trial)[(trial*5+3)%16];clip=[3,4,57,39]if trial%2 else[0,0,64,48]
        for y in range(48):
            for x in range(64):
                value=(0,0,0,0)
                if clip[0]<=x<clip[0]+clip[2]and clip[1]<=y<clip[1]+clip[3]:
                    if consumer:
                        for logical,slot in enumerate((0,1,3)):
                            if reason(trial,slot,choice(trial,logical,mode),mode):continue
                            x0,y0,x1,y1=RECTS[logical]
                            if x0<=x<x1 and y0<=y<y1:
                                side=(x+.5-x0)/(x1-x0)>(y+.5-y0)/(y1-y0)
                                if side==bool((v>>logical)&1):value=color(trial,logical,x,y,mode)
                    if x<8:value=(.875,.625,.625,1)
                pixels.extend(value)
        payloads['image']=b'\xa5'*256+struct.pack('<12288f',*pixels)+b'\xa5'*256
        for name,raw in payloads.items():(out/f'trial-{trial}.{name}.bin').write_bytes(raw)
        rows.append(dict(trial=trial,command_status=4,native_reference=native,producer_dispatches=int(trial!=7 and mode!='no_producer'),consumer_encoded=consumer,identifiers=ids,foreign_identifiers=foreign,scissor=clip,
            classes_restored_before_commit=True,autorelease_pool_drained_before_commit=True,scope_deallocated_before_commit=True,ICBs_deallocated_before_commit=True,sampler_0_alive_before_commit=True,sampler_1_alive_before_commit=True,api_refusals=[]))
    return dict(status='COMPLETED',mode=mode,device='NVIDIA GeForce GTX 880M',registry_id=1,
        device_identity=dict(schema=1,name='NVIDIA GeForce GTX 880M',registry_id=1,PCI_registry_id=2,PCI_vendor_id=0x10de,PCI_device_id=0x1198),runs=rows,scope_events=events,GPU_choice_CPU_read=False,CPU_resolved_state_supplied=native,native_Apple_ICB_ABI=False,performance_benchmark=False)


class RenderStateEvidence(unittest.TestCase):
    def test_valid_independent_dimensions_and_controls(self):
        for mode in ['release','native','pipeline_only','resources_only','forced_0','forced_1','no_producer','no_consumer']:
            with self.subTest(mode=mode),tempfile.TemporaryDirectory()as path:
                self.assertEqual(verify_rows(fixture(path,mode),path)['maximum_error'],0)

    def corrupt(self,name,offset,word=None,trial=0,mode='release'):
        with tempfile.TemporaryDirectory()as path:
            root=Path(path);d=fixture(root,mode);p=root/'outputs'/f'trial-{trial}.{name}.bin';raw=bytearray(p.read_bytes())
            if word is None:raw[offset]^=1
            else:struct.pack_into('<I',raw,offset,word)
            p.write_bytes(raw)
            with self.assertRaises(AssertionError):verify_rows(d,root)

    def test_background_alpha_must_be_explicit_zero(self):self.corrupt('image',256+32*16+12,0x3f800000)
    def test_native_arguments_cannot_select_both_candidates(self):self.corrupt('arguments',64,3)
    def test_gpu_state_identity_checked_in_source(self):self.corrupt('records',64+32)
    def test_foreign_catalogue_identity_is_preserved_as_rejected(self):self.corrupt('arguments',64+6*32,3,2,'gpu')
    def test_unknown_identity_reason_cannot_be_hidden(self):self.corrupt('witness',64+2*16+12,0x4b530000,1,'gpu')
    def test_cpu_template_limits_checked(self):self.corrupt('templates',0,7)
    def test_template_identity_checked(self):self.corrupt('templates',32)
    def test_opaque_identity_upload_checked(self):self.corrupt('identities',64)
    def test_private_material_parameters_checked(self):self.corrupt('state-1.parameters-1',256)
    def test_vertex_resource_bank_checked(self):self.corrupt('state-1.vertex-0',64+5*32+16)
    def test_texture_bank_checked(self):self.corrupt('texture-1',0)
    def test_argument_padding_guard_checked(self):self.corrupt('arguments',64+20)
    def test_witness_end_guard_checked(self):self.corrupt('witness',255)
    def test_nan_cannot_pass_numeric_comparison(self):self.corrupt('image',256,0x7fc00000)

    def test_reused_process_local_tokens_rejected(self):
        with tempfile.TemporaryDirectory()as path:
            d=fixture(path,'gpu');d['runs'][1]['identifiers']=d['runs'][0]['identifiers']
            with self.assertRaises(AssertionError):verify_rows(d,path)

    def test_cpu_choice_or_retained_software_owner_not_accepted(self):
        for key in ['GPU_choice_CPU_read','scope_deallocated_before_commit','ICBs_deallocated_before_commit','sampler_1_alive_before_commit']:
            with self.subTest(key=key),tempfile.TemporaryDirectory()as path:
                d=fixture(path)
                if key=='GPU_choice_CPU_read':d[key]=True
                else:d['runs'][0][key]=False
                with self.assertRaises(AssertionError):verify_rows(d,path)

    def test_fixed_shading_samples_separate_pipeline_and_resources(self):
        self.assertEqual(color(0,0,31,0,'release'),(.2421875,.353515625,.16015625,1))
        self.assertEqual(color(0,1,32,1,'release'),(.390625,.4375,.0478515625,1))
        self.assertEqual(color(0,2,20,20,'release'),(.0947265625,.12109375,1.0244140625,1))
        self.assertEqual(color(0,0,31,0,'pipeline_only'),(.166015625,.0009765625,.216796875,1))
        self.assertEqual(color(0,0,31,0,'resources_only'),(.1875,.359375,.203125,1))


if __name__=='__main__':unittest.main()
