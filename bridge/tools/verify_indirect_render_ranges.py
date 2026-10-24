#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU range, native draw arguments, guards and constant-rectangle raster oracle."""
from pathlib import Path
import math
import struct
from public_large_scratch import read,sha
from verify_local_memory import verify_device_identity

MODES=("gpu","native","no_consumer","lifetime","contracts","fragment","fragment_native","fragment_lifetime","legacy","legacy_native","release","fragment_release","records","records_native","fragment_records","fragment_records_native","records_no_consumer","records_no_producer","records_release","fragment_records_release")


def values(trial):return[((0x13579bd+i*97+trial*17)&0xffffffff)^0xa3b5c7d9 for i in range(16)]


def requested(trial,records=False,no_producer=False):
    if records:return (0,0 if trial==7 or no_producer else 4)
    v=values(trial)[(trial*5+3)%16]
    return [(0,4),(v%4,1),(0,1+v%4),(v%4,4-v%4),(v%4,0),(5,0),(0xfffffffe,3),(0,0)][trial]


def expected_buffers(trial,legacy=False,records=False,no_producer=False):
    def rectangle(first,indexed,rect,color):
        data=bytearray(b'\xa5'*4096);x0,y0,x1,y1=rect;xy=[(x0,y1),(x1,y1),(x0,y0),(x1,y0)];order=range(4)if indexed else[0,1,2,2,1,3]
        for i,j in enumerate(order):
            x,y=xy[j];struct.pack_into('<8f',data,64+(first+i)*32,x/32-1,1-y/24,.5,1,*color)
        return data
    result=[rectangle(5,False,(0,0,32,48),(.25,.125,.75,1)),rectangle(7,True,(32,0,64,48),(.125,.75,.25,1)),rectangle(3,True,(16,12,48,36),(.75,.5,.125,1))]
    inst=bytearray(b'\xa5'*512);inst[128:256]=bytes(128);result.append(inst)
    for format_ in ['H','I']:
        data=bytearray(b'\xa5'*256);raw=struct.pack('<6'+format_,*([0,1,2,2,1,3]if legacy else[5,6,7,7,6,8]));data[64:64+len(raw)]=raw;result.append(data)
    result.append(rectangle(0,False,(0,0,8,48),(.25,.125,.75,1)))
    marker=bytearray(b'\xa5'*512);struct.pack_into('<4f',marker,128,0,0,.625,0);result.append(marker)
    data=bytearray(b'\xa5'*192);data[64:128]=struct.pack('<16I',*values(trial));result.append(data)
    data=bytearray(b'\xa5'*136);struct.pack_into('<2I',data,64,*requested(trial,records,no_producer));result.append(data)
    data=bytearray(b'\xa5'*132);struct.pack_into('<I',data,64,0 if trial==7 or no_producer else values(trial)[(trial*5+3)%16]^0x4b505257);result.append(data)
    if records:
        data=bytearray(b'\xa5'*256)
        for slot in range(4):struct.pack_into('<8I',data,64+slot*32,*expected_record(trial,slot,not no_producer and trial!=7))
        result.append(data)
    return result


def expected_record(trial,slot,producer=True):
    if not producer or slot==2:return [0]*8
    kind={0:0,1:1,3:2}[slot];value=values(trial)[(trial*5+3)%16]
    record=[0x4b505244,kind,3,1,(5 if slot==0 else 0)+3*((value>>kind)&1),0 if slot==0 else 2 if slot==1 else 0xfffffffe,0 if slot==0 else 1 if slot==1 else 2,0]
    if trial==1 and slot==1:record[0]=0
    if trial==2 and slot==3:record[1]=1
    if trial==3 and slot==0:record[2]=0xfffffffe
    if trial==4 and slot==1:record[4]=0xfffffffe
    if trial==5 and slot==3:record[5]=0
    if trial==6 and slot==0:record[3]=2
    return record


def record_reason(trial,slot,producer=True):
    if slot==2:return 4
    if not producer:return 1
    return {(1,1):1,(2,3):2,(3,0):3,(4,1):3,(5,3):3,(6,0):3}.get((trial,slot),0)


def texel(bank,x,y):
    x,y=max(0,min(63,x)),max(0,min(47,y))
    return ((7-x%8)/8,(7-y%8)/8,((2*x+y)%8)/8,1)if bank else(x%8/16,y%8/16,(x+y)%8/16,1)


def fragment_color(slot,x,y,color):
    i={0:0,1:1,3:2}[slot];bank=int(i==1)
    if i==1:
        samples=[texel(bank,x,y),texel(bank,x+1,y),texel(bank,x,y+1),texel(bank,x+1,y+1)]
        sample=[sum(samples[k][c]*w for k,w in enumerate([.75*.875,.25*.875,.75*.125,.25*.125]))for c in range(4)]
    else:sample=texel(bank,x,y)
    scales=[(.5,1,1,1),(1,1.5,.5,1),(.75,.5,2,1)];biases=[(.125,0,0,0),(0,.125,0,0),(0,0,.25,0)]
    return tuple(sample[c]*color[c]*scales[i][c]+biases[i][c]for c in range(4))


def verify_rows(d,out):
    out=Path(out);verify_device_identity(d)
    assert d['status']=='COMPLETED'and d['scope_restored']is True and d['range_CPU_read_before_render']is False and d['performance_benchmark']is False
    mode=d['mode'];assert mode in MODES;assert d['CPU_resolved_range_supplied']is(mode=='native'or mode.endswith('_native'))
    reference=mode=='native'or mode.endswith('_native');fragment=mode.startswith('fragment');legacy=mode.startswith('legacy')
    records='records'in mode;no_producer=mode=='records_no_producer';consumer=mode not in ['no_consumer','records_no_consumer']
    release=mode.endswith('release');trials=1 if release else 8
    assert len(d['runs'])==trials;checked=guards=draws=0;max_error=0;files={}
    occupied={0:(0,0,32,48,(.25,.125,.75,1)),1:(32,0,64,48,(.125,.75,.25+1/64,1)),3:(16,12,48,36,(.75,.5,.125+2/64,1))}
    templates=[[3,1,0,0,0],[3,1,0,0,0],[0]*5,[3,1,0,0,0]]if legacy else[[6,1,5,0,0],[6,1,0,2,1],[0]*5,[6,1,0,0xfffffffe,2]];kinds=[0,1,0,2]
    for trial,r in enumerate(d['runs']):
        assert r['trial']==trial and r['command_status']==4 and r['expected_range']==list(requested(trial,records,no_producer))
        assert r['fragment_resources']is fragment and r['legacy_geometry']is legacy and r['inline_marker_parameter']is bool(trial%2)
        assert r['native_reference']is reference and r['consumer_encoded']is consumer and r['producer_dispatches']==(0 if trial==7 or no_producer else 1)
        first,count=requested(trial,records,no_producer);valid=first<=4 and count<=4-min(first,4)
        selected=[i for i in occupied if valid and first<=i and i-first<count and(not records or record_reason(trial,i,trial!=7 and not no_producer)==0)]
        scissor=[3,4,57,39]if trial%2 else[0,0,64,48];assert r['scissor']==scissor
        for i,expected in enumerate(expected_buffers(trial,legacy,records,no_producer)):
            p=out/'outputs'/f'trial-{trial}.buffer-{i}.bin';assert p.read_bytes()==expected,(trial,i);files[p.name]=sha(p)
        if not reference:
            p=out/'outputs'/f'trial-{trial}.arguments.bin';args=p.read_bytes();assert len(args)==256 and args[:64]==args[192:]==b'\xa5'*64
            p2=out/'outputs'/f'trial-{trial}.witness.bin';w=p2.read_bytes();assert len(w)==192 and w[:64]==w[128:]==b'\xa5'*64
            for slot in range(4):
                words=expected_record(trial,slot,trial!=7 and not no_producer)[2:7]if records else templates[slot]
                assert struct.unpack_from('<8I',args,64+slot*32)==tuple((words if slot in selected else[0]*5)+[0xa5a5a5a5]*3)
                tag=(0x4b520000|record_reason(trial,slot,trial!=7 and not no_producer))if records else 0x4b505247
                assert struct.unpack_from('<4I',w,64+slot*16)==(int(valid),int(slot in selected),kinds[slot],tag)
            files[p.name]=sha(p);files[p2.name]=sha(p2);guards+=256+48
        if fragment:
            for bank in range(2):
                p=out/'outputs'/f'trial-{trial}.texture-{bank}.bin';raw_texture=p.read_bytes();expected=[]
                for y in range(48):
                    for x in range(64):expected.extend(texel(bank,x,y))
                assert raw_texture==struct.pack('<12288f',*expected);files[p.name]=sha(p)
        p=out/'outputs'/f'trial-{trial}.image.bin';raw=p.read_bytes();assert len(raw)==49664 and raw[:256]==raw[-256:]==b'\xa5'*256;files[p.name]=sha(p)
        actual=struct.unpack('<12288f',raw[256:-256])
        for y in range(48):
            for x in range(64):
                color=(0,0,0,0)
                if scissor[0]<=x<scissor[0]+scissor[2]and scissor[1]<=y<scissor[1]+scissor[3]:
                    if consumer:
                        for slot in selected:
                            x0,y0,x1,y1,c=occupied[slot]
                            if legacy:color=(.75,.125,.25,1)
                            elif x0<=x<x1 and y0<=y<y1:
                                inside=True
                                if records:
                                    start=expected_record(trial,slot)[4]-(5 if slot==0 else 0)
                                    lhs=(2*x+1-2*x0)*(y1-y0);rhs=(2*y+1-2*y0)*(x1-x0)
                                    assert lhs!=rhs  # These fixture extents avoid diagonal pixel-center ties.
                                    inside=lhs<rhs if start==0 else lhs>rhs
                                if inside:color=fragment_color(slot,x,y,c)if fragment else c
                    if x<8:color=(.875,.625,.625,1)
                for c in range(4):
                    value=actual[(y*64+x)*4+c];error=abs(value-color[c]);assert math.isfinite(value)and error<=2e-6,(trial,x,y,c,value,color[c]);max_error=max(max_error,error);checked+=1
        draws+=len(selected)if consumer else 0;guards+=512
    if mode.endswith('lifetime'):
        assert len({r['ICB_object_identity']for r in d['runs']})==1
        assert [r['released_before_commit']for r in d['runs']]==[False]*7+[True]
        assert d['runs'][-1]['classes_restored_before_commit']is True
    if release:
        row=d['runs'][0]
        for key in ['released_before_commit','classes_restored_before_commit','autorelease_pool_drained_before_commit','scope_deallocated_before_commit','ICB_deallocated_before_commit']:assert row[key]is True,key
        assert row['fragment_texture_alive_before_commit']is fragment
        assert row['fragment_sampler_alive_before_commit']is fragment
    if mode=='contracts':
        expected=['pending_reprepare','misaligned_range','short_range','foreign_queue','unretained_command_buffer','wrong_kernel_pin','wrong_range_object','wrong_range_offset','copied_ICB_has_no_preparation','mutated_command','duplicate_execution']
        reset_expected=expected.copy();reset_expected[9]='reset_command'
        assert [r['api_refusals']for r in d['runs']]==[expected,reset_expected]+[[]for _ in range(6)]
    events=d['scope_events'];prepare=[e for e in events if e['operation']=='prepare_GPU_indirect_render_range'];execute=[e for e in events if e['operation']=='execute_GPU_indirect_render_range']
    assert len(prepare)==(0 if reference else trials)and len(execute)==(trials if not reference and consumer else 0)
    for e in prepare:assert e.get('GPU_generated_draw_records',False)is records
    for e in execute:
        assert e.get('GPU_generated_draw_records',False)is records and e.get('record_CPU_read',False)is False
        assert e['slot_capacity']==4 and e['range_offset']==64
        assert e['range_CPU_read']is False and e['caller_pipeline_restored']is True and e['caller_vertex_slots_restored']==(0 if legacy else 2)and e['caller_fragment_slots_restored']==(1 if fragment else 0)
        proof=e['evidence'];assert proof['operation']=='native_GPU_range_indirect_draws'and proof['resource_leases_until_completion']is True and proof['system_modified']is False
        assert proof['range_CPU_read']is False and proof['draw_arguments_CPU_read']is False and proof['raw_record_copies']==0
        assert [(r['slot'],r['kind'],r['argument_offset'])for r in proof['draw_calls']]==[(0,0,64),(1,1,96),(3,2,160)]
    return dict(status='PASS',mode=mode,checked_float_channels=checked,guard_bytes=guards,expected_nonzero_ICB_draws=draws,maximum_error=max_error,files_SHA256=files,performance_benchmark=False)


def verify_provenance(out):
    out=Path(out);m=read(out/'inputs.json');receipt=read(out/'execution/manifest.json')
    assert receipt['exit_code']==0 and receipt['SIGKILL_requested']is False and receipt['authoritative_ps_status']==''
    lease=receipt['GPU_reservation'];assert lease['state']=='terminal'and lease['child_PID']==receipt['pid']and lease['exit_code']==0 and lease['SIGKILL_requested']is False and not lease['known_signed_processes_live']
    assert receipt['arguments']==list(map(str,[out/'assets',out/'outputs',m['mode']]))
    assert sha(out/'application')==m['executable_SHA256']==receipt['original_binary_sha256']
    assert sha(out/'execution/application')==receipt['signed_binary_sha256']==lease['signed_binary_sha256']
    assert (out/'results.json').read_bytes()==(out/'execution/execution.stdout').read_bytes() or read(out/'results.json')==read(out/'execution/execution.stdout')
    assert read(out/'results.json')['mode']==m['mode']
    for key,folder in [('source_SHA256',''),('runtime_SHA256','runtime'),('oracle_SHA256','oracles'),('assets_SHA256','assets'),('runtime_sources_SHA256','library-src')]:
        for name,digest in m[key].items():
            p=out/folder/name;assert p.resolve().is_relative_to(out.resolve())and sha(p)==digest,(key,name)
    assert set(m['runtime_SHA256'])=={'run_sdk_host.py','lab_gpu_reservation.py'}
    assert receipt['launcher_SHA256']==m['runtime_SHA256']['run_sdk_host.py']and receipt['reservation_module_SHA256']==m['runtime_SHA256']['lab_gpu_reservation.py']
    library=read(out/'runtime-manifest.json')
    assert sha(out/'runtime-manifest.json')==m['library_manifest_SHA256']and library['static_library_SHA256']==m['static_library_SHA256']
    assert library['source_SHA256']==m['runtime_sources_SHA256']and library['status']=='PASS'and len(library['object_SHA256'])==7
    return m,receipt


def verify(out):
    verify_provenance(out)
    return verify_rows(read(Path(out)/'results.json'),out)
