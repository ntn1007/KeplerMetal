#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check five narrow P-picture proposals against trace-derived and Mesa oracles."""
import argparse
import base64
import ctypes
import json
import re
import struct
import subprocess
from pathlib import Path
from validate_baseline import EXPECTED, fields, need, sha

HERE=Path(__file__).resolve().parent
NAMES=('H264Stream.h','H264Stream.cpp','H264Baseline.h','H264Baseline.cpp','VideoLayout.h','VideoLayout.cpp',
       'VideoPicture.h','VideoPicture.cpp','VideoIdr.h','VideoIdr.cpp','VideoPredictive.h','VideoPredictive.cpp',
       'predictive_picture_tool.cpp','test_video_predictive.cpp','validate_video_predictive.py')


def run(label,args,out):
    p=subprocess.run(list(map(str,args)),capture_output=True,timeout=120)
    (out/(label+'.stdout')).write_bytes(p.stdout);(out/(label+'.stderr')).write_bytes(p.stderr)
    need(p.returncode==0 and not p.stderr,label+' failed; inspect retained stderr')
    return p.stdout


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('fixture','reference','baseline','idr-regression','vp-baseline','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();need(a.out.parent.is_dir() and not a.out.exists(),'fresh output required')
    before={n:sha(HERE/n) for n in NAMES}
    need({x.name:sha(x) for x in a.fixture.iterdir() if x.is_file()}==EXPECTED,'fixture differs')
    baseline=json.loads((a.baseline/'validation.json').read_text())
    need(baseline['status']=='PASS_SIX_FFMPEG_BASELINE_HEADERS_CPU' and
         all(baseline['source_sha256'][n]==before[n] for n in ('H264Stream.h','H264Stream.cpp','H264Baseline.h','H264Baseline.cpp','VideoLayout.h','VideoLayout.cpp')),'baseline differs')
    capture=json.loads((a.reference/'receipt.json').read_text());trace=a.reference/'trace.txt'
    need(sha(a.reference/'receipt.json')==baseline['reference_receipt_sha256'] and sha(trace)==capture['trace_sha256']==baseline['reference_trace_sha256'],'trace differs')
    idr=json.loads((a.idr_regression/'validation.json').read_text())
    need(idr['status']=='PASS_REAL_IDR_VP_CPU' and idr['baseline_receipt_sha256']==sha(a.baseline/'validation.json') and idr['mesa_helper_bytes_match'],'IDR regression differs')
    vp=json.loads((a.vp_baseline/'validation.json').read_text());ref=a.vp_baseline/'mesa-vp-reference.private.c'
    need(vp['status']=='PASS_MESA_VP_BLOCKS_CPU' and sha(ref)==vp['generated_reference_sha256'] and
         all(vp['source_sha256'][n]==before[n] for n in ('H264Stream.h','VideoLayout.h','VideoLayout.cpp','VideoPicture.h','VideoPicture.cpp')),'Mesa reference differs')
    text=trace.read_text();sp=fields(text.split('Sequence Parameter Set',1)[1].split('Picture Parameter Set',1)[0]);pp=fields(text.split('Picture Parameter Set',1)[1].split('Stream mapping:',1)[0])
    need(sp['profile_idc']==66 and sp['max_num_ref_frames']==2 and sp['pic_order_cnt_type']==0 and
         sp['frame_mbs_only_flag']==1 and pp['num_ref_idx_l0_default_active_minus1']==0 and
         pp['entropy_coding_mode_flag']==0 and pp['weighted_pred_flag']==0 and pp['weighted_bipred_idc']==0,
         'fixture profile differs')
    packets=re.split(r'\[trace_headers @ [^\]]+\] Packet:',text)[1:];need(len(packets)==6,'packet count differs')
    for i in range(1,6):
        slices=[fields(x) for x in packets[i].split('Slice Header')[1:]]
        need(len(slices)==2 and [s['first_mb_in_slice'] for s in slices]==[0,150] and all(
            s['nal_unit_type']==1 and s['nal_ref_idc']!=0 and s['slice_type']==0 and s['frame_num']==i and
            s['pic_order_cnt_lsb']==2*i and s['delta_pic_order_cnt_bottom']==0 and
            s['num_ref_idx_active_override_flag']==0 and s['ref_pic_list_modification_flag_l0']==0 and
            s['adaptive_ref_pic_marking_mode_flag']==0 for s in slices),'P slice trace differs')
    params=[a.baseline/('param-%d.bin'%i) for i in range(2)];meta=json.loads((a.fixture/'fixture.json').read_text())
    need(all(params[i].read_bytes()==base64.b64decode(meta['H264_parameter_sets_base64'][i],validate=True) for i in range(2)),'parameters differ')
    a.out.mkdir();flags=['-std=c++17','-Wall','-Wextra','-Werror','-O1','-g','-fsanitize=undefined','-fno-sanitize-recover=all']
    sources=[HERE/n for n in ('H264Stream.cpp','H264Baseline.cpp','VideoLayout.cpp','VideoPicture.cpp','VideoIdr.cpp','VideoPredictive.cpp')]
    run('build-test',['xcrun','clang++',*flags,*sources,HERE/'test_video_predictive.cpp','-o',a.out/'test'],a.out)
    run('test',[a.out/'test'],a.out)
    run('build-tool',['xcrun','clang++',*flags,*sources,HERE/'predictive_picture_tool.cpp','-o',a.out/'tool'],a.out)
    lines=run('prepare',[a.out/'tool',*params,a.fixture,a.out],a.out).decode().splitlines();need(len(lines)==5,'proposal count differs')
    run('build-mesa',['xcrun','clang','-std=gnu11','-dynamiclib',ref,'-o',a.out/'mesa.dylib'],a.out)
    lib=ctypes.CDLL(str((a.out/'mesa.dylib').resolve()));fn=lib.mesa_vp_reference
    fn.argtypes=[ctypes.POINTER(ctypes.c_uint32),ctypes.POINTER(ctypes.c_uint8),ctypes.POINTER(ctypes.c_uint8),ctypes.POINTER(ctypes.c_uint32)];fn.restype=ctypes.c_uint32
    w=(sp['pic_width_in_mbs_minus1']+1)*16;h=(sp['pic_height_in_map_units_minus1']+1)*16
    wmb=(w+15)//16;hmb=(h+15)//16;half_w=(w+31)//32;half_h=(h+31)//32;aligned_h=((h+63)//64)*64
    inter=((w*h*2+(4<<20)-1)//(4<<20))*(4<<20);chroma=pp['chroma_qp_index_offset'];qp=pp['pic_init_qp_minus26']
    rows=[]
    for i,line in enumerate(lines,1):
        count=1 if i==1 else 2;target=i%3;need(json.loads(line)=={'frame':i,'poc':2*i,'refs':count,'target_slot':target,'simple':1,'caps':0x1113},'proposal fields differ')
        b=bytearray(756);put=lambda pos,v:struct.pack_into('<I',b,pos,v&0xffffffff)
        struct.pack_into('<HH',b,0,wmb,hmb);put(4,wmb*16);put(8,wmb*16)
        y2=half_h*wmb;cbcr=2*y2;cbcr2=cbcr+wmb*(aligned_h//64)
        put(0x10,y2);put(0x18,cbcr);put(0x1c,cbcr2);put(0x20,cbcr);put(0x24,(16*half_w*aligned_h*3//2)//256)
        put(0x28,wmb*3);put(0x2c,inter//256-wmb*3-4)
        flags=(sp['direct_8x8_inference_flag']<<1)|(pp['weighted_pred_flag']<<2)|(pp['constrained_intra_pred_flag']<<3)|16|\
              (sp['log2_max_frame_num_minus4']<<8)|(1<<12)|(sp['pic_order_cnt_type']<<14)|((qp&63)<<16)|((chroma&31)<<22)|((chroma&31)<<27)
        put(0x30,flags);put(0x34,(target<<9)|(i<<14));put(0x38,2*i);put(0x3c,2*i)
        x=(ctypes.c_uint32*256)();x[0]=w;x[1]=h;x[2]=2;x[3]=2;x[4]=count;x[5]=target
        x[6]=(sp['direct_8x8_inference_flag']<<1)|(pp['weighted_pred_flag']<<2)|(pp['constrained_intra_pred_flag']<<3)|16
        x[7]=sp['log2_max_frame_num_minus4'];x[8]=sp['pic_order_cnt_type'];x[9]=qp&0xffffffff;x[10]=chroma&0xffffffff;x[11]=chroma&0xffffffff
        x[12]=pp['weighted_bipred_idc'];x[13]=i;x[14]=x[15]=2*i
        for j,frame in enumerate(range(i-count,i)):
            slot=frame%3;position=0x40+16*j;word=(j+1)|(slot<<7)|(1<<12)|(1<<13)|(1<<17)|(1<<21)
            put(position,word);put(position+4,2*frame);put(position+8,2*frame);put(position+12,frame)
            x[32+slot]=6;rx=64+5*j;x[rx]=slot;x[rx+1]=3;x[rx+2]=x[rx+3]=2*frame;x[rx+4]=frame
        b[0x140:0x220]=bytes([16])*224
        actual=(a.out/('p-%03d.bin'%i)).read_bytes();need(actual==bytes(b),'trace-derived block differs')
        scale=(ctypes.c_uint8*224)(*([16]*224));aligned=(ctypes.c_uint32*189)();raw=ctypes.cast(aligned,ctypes.POINTER(ctypes.c_uint8));after=ctypes.c_uint32()
        caps=fn(x,scale,raw,ctypes.byref(after));need(caps==0x1113 and after.value==6 and bytes(raw[:756])==actual,'Mesa block differs')
        rows.append({'frame':i,'reference_count':count,'target_slot':target,'block_sha256':sha(a.out/('p-%03d.bin'%i))})
    need({n:sha(HERE/n) for n in NAMES}==before and sha(ref)==vp['generated_reference_sha256'],'inputs changed')
    result={'status':'PASS_FIVE_BASELINE_P_PROPOSALS_CPU','frames':5,'slice_headers':10,'block_bytes':756,'rows':rows,
        'fixture_assumed_reference_state':'chronological two-short-term sliding window; logical completion simulated',
        'actual_decoded_reference_ownership_proved':False,'ffmpeg_trace_fields_match':True,'trace_derived_bytes_match':True,
        'mesa_helper_bytes_match':True,'complete_h264_validation':False,'gpu_transport_implemented':False,
        'hardware_video_execution_proved':False,'system_modified':False,'baseline_sha256':sha(a.baseline/'validation.json'),
        'idr_regression_sha256':sha(a.idr_regression/'validation.json'),'mesa_reference_sha256':sha(ref),
        'trace_sha256':sha(trace),'source_sha256':before}
    (a.out/'validation.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps(result,sort_keys=True))


if __name__=='__main__':main()
