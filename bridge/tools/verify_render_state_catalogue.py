#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent input/record/template/argument and raster oracle; no GPU calls."""
from pathlib import Path
import math
import struct
from public_large_scratch import read,sha
from verify_indirect_render_ranges import verify_provenance,values,expected_buffers,texel
from verify_local_memory import verify_device_identity

MODES=('gpu','native','pipeline_only','pipeline_only_native','resources_only','resources_only_native',
       'forced_0','forced_1','no_producer','no_consumer','release','contracts')
RECTS=((0,0,32,48),(32,0,64,48),(16,12,48,36))
COLORS=(((.25,.125,.75,1),(.125,.75,.25,1),(.75,.5,.125,1)),
        ((.5,.375,.25,1),(.375,.25,.5,1),(.125,.5,.625,1)))
SCALES=((.5,1,1,1),(1,1.5,.5,1),(.75,.5,2,1))
BIASES=((.125,0,0,0),(0,.125,0,0),(0,0,.25,0))


def choice(trial,logical,mode):
    if mode=='forced_0':return 0
    if mode=='forced_1':return 1
    return (values(trial)[(trial*5+3)%16]>>(logical+3))&1


def source_record(trial,slot,mode,ids,foreign,reset_slot=None):
    producer=trial!=7 and mode!='no_producer'
    if not producer or slot==2 or slot==reset_slot:return bytes(64)
    logical={0:0,1:1,3:2}[slot];state=choice(trial,logical,mode)
    v=values(trial)[(trial*5+3)%16]
    words=[0x4b505353,logical,3,1,(5 if logical==0 else 0)+3*((v>>logical)&1),
           0 if logical==0 else 2 if logical==1 else 0xfffffffe,logical,0]
    identity=ids[state];reserved=[0]*6
    if trial==1 and slot==1:identity=0
    if trial==2 and slot==3:identity=foreign[state]
    if trial==3 and slot==0:words[1]=1
    if trial==4 and slot==1:words[4]=0xfffffffe
    if trial==5 and slot==3:reserved[0]=1
    if trial==6 and slot==0:identity^=1<<32
    return struct.pack('<8IQ6I',*words,identity,*reserved)


def reason(trial,slot,state,mode,reset_slot=None):
    if slot==2:return 4
    if slot==reset_slot:return 1
    if trial==7 or mode=='no_producer':return 1
    if (trial,slot)in [(1,1),(2,3),(6,0)]:return 5
    if (trial,slot)==(5,3):return 1
    logical={0:0,1:1,3:2}[slot]
    if state!=choice(trial,logical,mode):return 6
    if (trial,slot)==(3,0):return 2
    if (trial,slot)==(4,1):return 3
    return 0


def scene_buffers(trial,mode,ids,foreign,reset_slot=None):
    old=expected_buffers(trial);pipeline_only=mode.startswith('pipeline_only')
    result={}
    for state in range(1 if pipeline_only else 2):
        for logical in range(3):
            raw=bytearray(old[logical]);first=(5,7,3)[logical]
            for i in range(6 if logical==0 else 4):struct.pack_into('<4f',raw,64+(first+i)*32+16,*COLORS[state][logical])
            result[f'state-{state}.vertex-{logical}']=raw
            raw=bytearray(b'\xa5'*512);bias=[BIASES[logical][c]+((.0625,.03125,.015625,0)[c]if state else 0)for c in range(4)]
            struct.pack_into('<8f',raw,256,*SCALES[logical],*bias);result[f'state-{state}.parameters-{logical}']=raw
    result.update(instances=old[3],**{'indices-0':old[4],'indices-1':old[5],'marker.vertices':old[6],'marker.parameters':old[7],'seeds':old[8]})
    for name,tokens in [('identities',ids),('foreign-identities',foreign)]:
        raw=bytearray(b'\xa5'*144);struct.pack_into('<2Q',raw,64,*tokens);result[name]=raw
    produce=trial!=7 and mode!='no_producer'
    raw=bytearray(b'\xa5'*136);struct.pack_into('<2I',raw,64,0,4 if produce else 0);result['range']=raw
    raw=bytearray(b'\xa5'*132);struct.pack_into('<I',raw,64,values(trial)[(trial*5+3)%16]^0x4b505357 if produce else 0);result['counter']=raw
    result['records']=b'\xa5'*64+b''.join(source_record(trial,slot,mode,ids,foreign,reset_slot)for slot in range(4))+b'\xa5'*64
    return result


def sample(bank,x,y,function):
    def at(x,y):return texel(bank,x%64,y%48)if bank else texel(bank,x,y)
    if function!=1:return at(x,y)
    corners=(at(x,y),at(x+1,y),at(x,y+1),at(x+1,y+1))
    weights=(.65625,.21875,.09375,.03125)
    return tuple(sum(p[c]*w for p,w in zip(corners,weights))for c in range(4))


def color(trial,logical,x,y,mode):
    state=choice(trial,logical,mode);resource=0 if mode.startswith('pipeline_only')else state
    function=((0,1,2),(1,0,1))[0 if mode.startswith('resources_only')else state][logical]
    sampled=sample(resource,x,y,function);base=list(COLORS[resource][logical]);base[2]+=logical/64
    bias=[BIASES[logical][c]+((.0625,.03125,.015625,0)[c]if resource else 0)for c in range(4)]
    return tuple(sampled[c]*base[c]*SCALES[logical][c]+bias[c]for c in range(4))


def verify_rows(d,out,reset_slot=None,extra_buffers=None):
    out=Path(out);verify_device_identity(d);mode=d['mode'];assert mode in MODES
    native=mode.endswith('native');trials=1 if mode=='release'else 8;consumer=mode!='no_consumer'
    assert d['status']=='COMPLETED'and d['GPU_choice_CPU_read']is False and d['CPU_resolved_state_supplied']is native
    assert d['native_Apple_ICB_ABI']is False and d['performance_benchmark']is False and len(d['runs'])==trials
    checked=guards=selected=rejected=0;max_error=0;files={};seen=set();creates=[]
    for trial,row in enumerate(d['runs']):
        assert row['trial']==trial and row['command_status']==4 and row['native_reference']is native
        assert type(row['producer_dispatches'])is int
        assert row['producer_dispatches']==int(trial!=7 and mode!='no_producer')and row['consumer_encoded']is consumer
        for name in ['classes_restored_before_commit','autorelease_pool_drained_before_commit','scope_deallocated_before_commit','ICBs_deallocated_before_commit','sampler_0_alive_before_commit','sampler_1_alive_before_commit']:assert row[name]is True,name
        if mode=='contracts':assert row['api_refusals']==(['duplicate_source','source_capacity','expanded_capacity','wrong_kernel_pin','wrong_execution_ICB','short_records','misaligned_records','misaligned_range','pending_preparation','wrong_range_object','wrong_range_offset','copy_has_no_preparation','mutated_alternative','duplicate_execution']if trial<2 else[])
        ids,foreign=row['identifiers'],row['foreign_identifiers'];tokens=ids+foreign
        assert len(ids)==len(foreign)==2 and len(set(tokens))==4
        assert all(type(i)is int and i>>32==0x4b505352 and i&0xffffffff and i not in seen for i in tokens)
        seen.update(tokens);creates.extend([foreign,ids])
        expected=scene_buffers(trial,mode,ids,foreign,reset_slot)
        if extra_buffers is not None:
            assert trial in extra_buffers and not(set(expected)&set(extra_buffers[trial]))
            expected.update(extra_buffers[trial])
        if not native:
            templates=bytearray();args=bytearray(b'\xa5'*384);witness=bytearray(b'\xa5'*256)
            maxima=([6,1,5,0,0],[6,1,0,2,1],[0]*5,[6,1,0,0xfffffffe,2]);kinds=(0,1,0,2)
            for slot in range(4):
                for state in range(2):
                    flat=slot*2+state;why=reason(trial,slot,state,mode,reset_slot);active=why==0 and trial!=7 and mode!='no_producer'
                    templates.extend(struct.pack('<8IQ6I',*maxima[slot],kinds[slot],int(slot!=2),0,ids[state],slot,0,0,0,0,0))
                    arguments=list(struct.unpack('<8IQ6I',source_record(trial,slot,mode,ids,foreign,reset_slot))[2:7])if active else[0]*5
                    struct.pack_into('<5I',args,64+flat*32,*arguments)
                    struct.pack_into('<4I',witness,64+flat*16,1,int(active),(slot<<16)|state,0x4b530000|why)
                    selected+=int(active);rejected+=int(why in [1,2,3,5])
            expected.update(templates=templates,arguments=args,witness=witness);guards+=128+8*12+128
        for bank in range(2):expected[f'texture-{bank}']=struct.pack('<12288f',*[v for y in range(48)for x in range(64)for v in texel(bank,x,y)])
        prefix=f'trial-{trial}.'
        assert {p.name for p in(out/'outputs').glob(prefix+'*.bin')}=={prefix+n+'.bin'for n in expected}|{prefix+'image.bin'}
        for name,want in expected.items():
            p=out/'outputs'/(prefix+name+'.bin');assert p.read_bytes()==want,(trial,name);files[p.name]=sha(p)
        scissor=[3,4,57,39]if trial%2 else[0,0,64,48];assert row['scissor']==scissor
        p=out/'outputs'/(prefix+'image.bin');raw=p.read_bytes();assert len(raw)==49664 and raw[:256]==raw[-256:]==b'\xa5'*256;files[p.name]=sha(p)
        actual=struct.unpack('<12288f',raw[256:-256]);v=values(trial)[(trial*5+3)%16]
        for y in range(48):
            for x in range(64):
                wanted=(0,0,0,0)
                if scissor[0]<=x<scissor[0]+scissor[2]and scissor[1]<=y<scissor[1]+scissor[3]:
                    if consumer:
                        for logical,slot in enumerate((0,1,3)):
                            if reason(trial,slot,choice(trial,logical,mode),mode,reset_slot):continue
                            x0,y0,x1,y1=RECTS[logical]
                            if x0<=x<x1 and y0<=y<y1:
                                side=(2*x+1-2*x0)*(y1-y0)>(2*y+1-2*y0)*(x1-x0)
                                if side==bool((v>>logical)&1):wanted=color(trial,logical,x,y,mode)
                    if x<8:wanted=(.875,.625,.625,1)
                for c in range(4):
                    value=actual[(y*64+x)*4+c];error=abs(value-wanted[c]);assert math.isfinite(value)and error<=2e-6,(trial,x,y,c,value,wanted[c]);max_error=max(max_error,error);checked+=1
        guards+=512
    events=d['scope_events'];creation=[e for e in events if e['operation']=='create_render_state_catalogue']
    assert [e['state_identifiers']for e in creation]==creates
    for e in creation:assert(e['logical_slots'],e['states'],e['native_slots'])==(4,2,8)and e['native_Apple_pipeline_resource_IDs']is False
    prepare=[e for e in events if e['operation']=='prepare_GPU_indirect_render_range'];execute=[e for e in events if e['operation']=='execute_GPU_indirect_render_range']
    assert len(prepare)==(0 if native else trials)and len(execute)==(trials if not native and consumer else 0)
    for e in prepare:assert(e['slots'],e['native_slots'])==(4,8)and e['GPU_state_selection']is True and e['GPU_generated_draw_records']is True and e['range_CPU_read']is False
    for e in execute:
        assert(e['slot_capacity'],e['native_slot_capacity'],e['state_count'])==(4,8,2)
        assert e['GPU_state_selection']is True and e['selection_CPU_read']is False and e['record_CPU_read']is False and e['range_CPU_read']is False
        assert e['state_selection_method']=='native_indirect_draw_predicates'and e['caller_pipeline_restored']is True and e['caller_vertex_slots_restored']==2 and e['caller_fragment_slots_restored']==1
        proof=e['evidence'];assert proof['raw_record_copies']==0 and proof['resource_leases_until_completion']is True and proof['draw_arguments_CPU_read']is False
        assert [(r['slot'],r['kind'],r['argument_offset'])for r in proof['draw_calls']]==[(0,0,64),(1,0,96),(2,1,128),(3,1,160),(6,2,256),(7,2,288)]
    return dict(status='PASS',mode=mode,checked_float_channels=checked,guard_bytes=guards,maximum_error=max_error,
        GPU_selected_candidate_records=selected if not native else 0,GPU_rejected_candidate_records=rejected if not native else 0,
        state_choice_CPU_read=False,native_Apple_ICB_ABI=False,performance_benchmark=False,files_SHA256=files)


def verify(out):
    verify_provenance(out)
    return verify_rows(read(Path(out)/'results.json'),out)
