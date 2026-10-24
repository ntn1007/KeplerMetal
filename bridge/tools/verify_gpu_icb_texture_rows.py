#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent CPU samples and GPU-side resource-choice evidence."""
from pathlib import Path
import base64
import struct
from public_large_scratch import sha

SENTINEL=0xd15ea5ed
MASK=0xffffffff
MODES=['gpu','gpu_wrong_texture','gpu_wrong_sampler','gpu_wrong_buffer','gpu_no_producer','gpu_no_consumer']


def reference(trial,n,mode):
    assert mode in MODES
    seed=0x125ab700+trial*97;bank=(n^seed^trial)&1
    ti=int(mode=='gpu_wrong_texture')^bank;si=int(mode=='gpu_wrong_sampler')^bank;bi=int(mode=='gpu_wrong_buffer')^bank
    output=[]
    for gid in range(n):
        x,y=(gid*3+trial)%12-4,(gid*5+trial*2)%12-4
        x,y=(x%4,y%4)if si else(max(0,min(3,x)),max(0,min(3,y)))
        value=(((gid+8)*747796405+seed)&MASK)^0x12345678^(0x2468ace1 if bi else 0)
        witnesses=[value^seed,gid*3,(value*5+trial)&MASK,0xc0010000^gid^0x00040104]
        for c,w in enumerate(witnesses):
            texel=(x*47+y*29+c*37+(91 if ti else 13))%256
            output.append(SENTINEL if mode in ['gpu_no_producer','gpu_no_consumer']else texel^w)
    return output


def verify_trace(d):
    producer=d['mode']!='gpu_no_producer';consumer=d['mode']!='gpu_no_consumer'
    assert d['status']=='PASS'and d['native_shader']is True and d['performance_benchmark']is False
    rows=lambda name:[e for e in d['scope_events']if e['operation']==name]
    registrations=rows('register_native_IRv2_function');assert len(registrations)==1
    reg=registrations[0];schema=reg['schema']
    assert reg['native_shader_compilation_replaced']is False and reg['native_reflection_reused']is True
    assert reg['library_SHA256']==d['producer_library_SHA256']and reg['function']=='encode_image_command'
    assert (schema['encoded_length'],schema['alignment'],schema['buffer_index'],schema['binding_count'])==(40,8,0,3)
    assert [(m['index'],m['offset'],m['type'])for m in schema['members']]==[(0,0,60),(1,8,85),(2,16,60),(3,24,60),(4,32,60)]
    assert d['native_library_factories']is True and d['manual_function_registrations']==0 and d['native_argument_encoder_restored']is True
    assert len(rows('register_native_source_IRv2_library'))==len(rows('automatic_IRv2_library'))==len(rows('automatic_IRv2_function'))==1
    restored=rows('scope_restore');assert len(restored)==1 and restored[0]['device_class_restored']is True and restored[0]['system_modified']is False
    executed=rows('executeCommandsInBuffer');assert len(executed)==(3 if consumer else 0)
    for e in executed:
        assert e['resident_GPU_descriptor']is True and e['executed_indices']==[1]
        p=e['evidence'];assert p['operation']=='resident_QMD_launch'and p['resident_launches']==1 and p['launch_suppressed']is False
        assert p['CPU_QMD_uploads_in_launch']==p['CPU_constant_uploads_in_launch']==p['native_preparation_GPU_dispatches']==0
        assert p['primer_comparison']['exact_bytes']is True and p['primer_comparison']['inactive_CB0_descriptor_normalized']is False and p['system_modified']is False
        assert p['owner_original_profiles']
        for owner in p['owner_original_profiles']:
            assert owner['original_record_function']=='sample_icb_arguments'and owner['native_register_count']==17 and owner['constant_buffer_valid_mask']==7
            literal=owner['native_literal_bank_0'];assert literal['bytes']==256 and literal['native_code_bytes']==1216 and literal['variant_owner_retained']is True
    for r in d['runs']:
        plan=lambda name:[e for e in r['plan_events']if e['operation']==name]
        encoded=plan('encode_public_IRv2_arguments');assert encoded and all(e['bytes']==40 and e['native_Apple_ICB_identity']is False for e in encoded)
        materialized=plan('GPU_command_IR_materialization');assert len(materialized)==1 and materialized[0]['record_CPU_read']is False and materialized[0]['rows']==1
        selection=plan('GPU_command_descriptor_selection');assert len(selection)==1;s=selection[0]
        assert s['producer_encoded']is producer and s['CPU_shadow_is_execution_source']is False and s['descriptor_CPU_upload']is False
        assert s['GPU_generated_resource_bindings']is True and s['choice_CPU_read']is False and s['candidate_count']==1


def verify_rows(d,outputs):
    outputs=Path(outputs);mode=d['mode'];assert mode in MODES
    producer=mode!='gpu_no_producer';assert len(d['runs'])==3 and[a['offset']for a in d['argument_layout']]==[0,8,16]
    checked=guards=0;files={};banks=[]
    word=lambda raw,o:struct.unpack_from('<I',raw,o)[0]
    address=lambda raw,o:struct.unpack_from('<Q',raw,o)[0]
    for trial,(r,n)in enumerate(zip(d['runs'],[16,65,257])):
        seed=0x125ab700+trial*97;bank=(n^seed^trial)&1;banks.append(bank);groups=(n+31)//32
        assert(r['trial'],r['threads'],r['seed'],r['expected_GPU_bank'])==(trial,n,seed,bank)
        assert r['mismatches']==r['output_guard_mismatches']==r['root_guard_mismatches']==0 and r['command_status']==4
        for key,suffix in [('texture','texture'),('sampler','sampler'),('input','buffer')]:assert r[key]==int(mode=='gpu_wrong_'+suffix)
        get=lambda suffix:(outputs/f'trial-{trial}.{suffix}.bin').read_bytes()
        raw=get('output');assert len(raw)==(((n+31)//32)*32+8)*16
        assert raw[:64]==struct.pack('<I',SENTINEL)*16 and raw[64+n*16:]==struct.pack('<I',SENTINEL)*((len(raw)-64-n*16)//4)
        assert list(struct.unpack('<'+'I'*n*4,raw[64:64+n*16]))==reference(trial,n,mode)
        for which,(root_name,private_name)in enumerate([('root','private-root'),('alternate-root','alternate-private-root')]):
            root,private=get(root_name),get(private_name);assert len(root)==152 and root==private and root[:64]==root[88:]==b'\xa5'*64
            prefix='alternate_'if which else''
            native=base64.b64decode(r[prefix+'native_bytes_base64'],validate=True);assert len(native)==24 and root[64:88]==native
            if not which:assert native==base64.b64decode(r['encoded_bytes_base64'],validate=True)
            assert word(native,0)==r[prefix+'texture_ID']>0 and word(native,8)==r[prefix+'sampler_ID']>0 and address(native,16)==r[prefix+'input_GPU_address_plus_offset']>32
        for which in range(2):
            data=get('input-'+str(which));values=[(((i*747796405+seed)&MASK)^0x12345678^(0x2468ace1 if which else 0))for i in range(n+32)]
            assert data==struct.pack('<'+'I'*len(values),*values)
        roots=r['argument_root_GPU_addresses_plus_offsets'];assert len(roots)==2 and roots[0]!=roots[1]
        params=get('parameters');assert len(params)==512 and params[:16]==struct.pack('<4I',n,seed,trial,0)
        assert address(params,16)==roots[1]and params[24:]==b'\xa5'*488
        producer_root=get('producer-root');assert len(producer_root)==168 and producer_root[:64]==producer_root[104:]==b'\xa5'*64
        root_values=struct.unpack('<5Q',producer_root[64:104]);assert root_values[0]==r['context_GPU_address']and root_values[1]>>32==0x4b505350 and root_values[1]&MASK
        assert root_values[2:]==(roots[0],r['output_GPU_address_plus_offset'],r['parameters_GPU_address'])
        context=get('context');assert len(context)==480
        assert struct.unpack_from('<4IQ2I',context)==(0x4b505343,3,1,3,r['records_GPU_address_plus_offset'],128,1)
        assert struct.unpack_from('<2Q10I',context,32)==(root_values[1],r['parameters_GPU_address'],groups,1,1,32,1,1,0,2,0,0)and context[88:]==bytes(392)
        records=get('records');assert len(records)==256 and records[:64]==records[192:]==b'\xa5'*64
        words=list(struct.unpack('<32I',records[64:192]));expected=[0]*32
        if producer:
            expected[:12]=[0x4b504952,115,0,0x4b504950,groups,1,1,0,32,1,1,0]
            for index,value in [(12,roots[bank]),(14,r['output_GPU_address_plus_offset']),(16,r['parameters_GPU_address'])]:expected[index:index+2]=[value&MASK,value>>32]
        assert words==expected
        witness=get('witness');assert len(witness)==192 and witness[:64]==witness[128:]==b'\xa5'*64
        actual_groups=groups if producer else 0
        assert struct.unpack('<16I',witness[64:128])==(actual_groups,1,1,0,32,1,1,bank if producer else 0,1 if producer else 2,0x4b504952,2,2,0,0,0,0x4b50524d)
        counts=get('counts');assert len(counts)==136 and counts[:64]==counts[72:]==b'\xa5'*64 and struct.unpack('<2I',counts[64:72])==(0,64)
        native,qmd=get('CB1'),get('QMD');assert len(native)==65536 and len(qmd)==4096
        if producer:
            for offset,value in [(8,roots[bank]),(40,r['output_GPU_address_plus_offset']),(72,r['parameters_GPU_address'])]:assert address(native,offset)==value
        assert word(qmd,0x30)==actual_groups and word(qmd,0xb8)>>24==17 and word(qmd,0x50)&255==7
        assert[word(native,o)for o in [0x720,0x724,0x728,0x740,0x744,0x748]]==[actual_groups*32,1,1,actual_groups,1,1]
        for suffix in ['output','root','private-root','alternate-root','alternate-private-root','parameters','input-0','input-1','records','witness','producer-root','counts','CB1','QMD','context']:
            p=outputs/f'trial-{trial}.{suffix}.bin';files[p.name]=sha(p)
        checked+=n*4;guards+=len(raw)-n*16+2*256+488+4*128
    return dict(checked_uint32=checked,guard_bytes=guards,selected_banks=banks,GPU_records_checked=3 if producer else 0,zero_CTA_records=0 if producer else 3,files_SHA256=files)
