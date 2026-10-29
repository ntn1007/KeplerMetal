#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare a real restricted IDR VP block with FFmpeg fields and Mesa."""
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
       'VideoPicture.h','VideoPicture.cpp','VideoIdr.h','VideoIdr.cpp','idr_picture_tool.cpp',
       'test_video_idr.cpp','validate_video_idr.py')

def run(label,args,out,expected=0):
    p=subprocess.run(list(map(str,args)),capture_output=True,timeout=120)
    (out/(label+'.stdout')).write_bytes(p.stdout); (out/(label+'.stderr')).write_bytes(p.stderr)
    need(p.returncode==expected and not p.stderr,label+' failed; inspect retained stderr')
    return p.stdout

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('fixture','reference','baseline','vp-baseline','out'): p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args(); need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required')
    before={n:sha(HERE/n) for n in NAMES}
    need({x.name:sha(x) for x in a.fixture.iterdir() if x.is_file()}==EXPECTED,'fixture differs')
    baseline=json.loads((a.baseline/'validation.json').read_text())
    need(baseline['status']=='PASS_SIX_FFMPEG_BASELINE_HEADERS_CPU' and
         all(baseline['source_sha256'][n]==before[n] for n in ('H264Stream.h','H264Stream.cpp','H264Baseline.h',
             'H264Baseline.cpp','VideoLayout.h','VideoLayout.cpp')),'baseline differs')
    receipt=json.loads((a.reference/'receipt.json').read_text())
    need(sha(a.reference/'receipt.json')==baseline['reference_receipt_sha256'] and
         sha(a.reference/'trace.txt')==receipt['trace_sha256']==baseline['reference_trace_sha256'],'trace differs')
    vp=json.loads((a.vp_baseline/'validation.json').read_text()); ref=a.vp_baseline/'mesa-vp-reference.private.c'
    need(vp['status']=='PASS_MESA_VP_BLOCKS_CPU' and sha(ref)==vp['generated_reference_sha256'] and
         all(vp['source_sha256'][n]==before[n] for n in ('H264Stream.h','VideoLayout.h','VideoLayout.cpp',
              'VideoPicture.h','VideoPicture.cpp')),'Mesa comparison differs')
    trace=(a.reference/'trace.txt').read_text()
    sp=fields(trace.split('Sequence Parameter Set',1)[1].split('Picture Parameter Set',1)[0])
    pp=fields(trace.split('Picture Parameter Set',1)[1].split('Stream mapping:',1)[0])
    packets=re.split(r'\[trace_headers @ [^\]]+\] Packet:',trace)[1:]
    need(len(packets)==6,'packet count differs')
    slices=[fields(s) for s in packets[0].split('Slice Header')[1:]]
    need(len(slices)==2 and all(s['nal_unit_type']==5 and s['nal_ref_idc']!=0 and s['slice_type']==2 and
        s['frame_num']==0 and s['pic_order_cnt_lsb']==0 and s['delta_pic_order_cnt_bottom']==0 and
        s['no_output_of_prior_pics_flag']==0 and s['long_term_reference_flag']==0 for s in slices),'IDR reference differs')
    need(sp['profile_idc']==66 and sp['pic_order_cnt_type']==0 and sp['frame_mbs_only_flag']==1 and
        pp['num_slice_groups_minus1']==0 and pp['bottom_field_pic_order_in_frame_present_flag']==1,'profile differs')
    a.out.mkdir(); flags=['-std=c++17','-Wall','-Wextra','-Werror','-O1','-g','-fsanitize=undefined','-fno-sanitize-recover=all']
    sources=[HERE/n for n in ('H264Stream.cpp','H264Baseline.cpp','VideoLayout.cpp','VideoPicture.cpp','VideoIdr.cpp')]
    run('build-test',['xcrun','clang++',*flags,*sources,HERE/'test_video_idr.cpp','-o',a.out/'test'],a.out)
    run('test',[a.out/'test'],a.out)
    run('build-tool',['xcrun','clang++',*flags,*sources,HERE/'idr_picture_tool.cpp','-o',a.out/'tool'],a.out)
    params=[a.baseline/('param-%d.bin'%i) for i in range(2)]
    fixture_meta=json.loads((a.fixture/'fixture.json').read_text())
    need(len(fixture_meta['H264_parameter_sets_base64'])==2 and all(
        params[i].read_bytes()==base64.b64decode(fixture_meta['H264_parameter_sets_base64'][i],validate=True)
        for i in range(2)),'parameter files differ from fixture')
    out=a.out/'idr-vp.bin'
    got=json.loads(run('idr',[a.out/'tool',*params,a.fixture/'frame-000.avcc',out],a.out))
    expected_info={'is_idr':1,'is_reference':1,'chroma_qp_offset':pp['chroma_qp_index_offset'],
        'constrained_intra':pp['constrained_intra_pred_flag'],'delta_poc_bottom':slices[0]['delta_pic_order_cnt_bottom'],
        'no_output_prior':slices[0]['no_output_of_prior_pics_flag'],'long_term':slices[0]['long_term_reference_flag'],'caps':0x1113}
    need(got==expected_info,'extracted fields differ from FFmpeg')
    for i in range(1,6):
        rejected=a.out/('rejected-%d.bin'%i)
        run('reject-%d'%i,[a.out/'tool',*params,a.fixture/('frame-%03d.avcc'%i),rejected],a.out,5)
        need(not rejected.exists(),'rejected frame created output')
    w=(sp['pic_width_in_mbs_minus1']+1)*16; h=(sp['pic_height_in_map_units_minus1']+1)*16
    wmb=(w+15)//16; hmb=(h+15)//16; half_w=(w+31)//32; half_h=(h+31)//32; aligned_h=((h+63)//64)*64
    inter=((w*h*2+(4<<20)-1)//(4<<20))*(4<<20)
    b=bytearray(756); put=lambda pos,v:struct.pack_into('<I',b,pos,v&0xffffffff)
    struct.pack_into('<HH',b,0,wmb,hmb); put(4,wmb*16); put(8,wmb*16)
    y2=half_h*wmb; cbcr=2*y2; cbcr2=cbcr+wmb*(aligned_h//64)
    put(0x10,y2); put(0x18,cbcr); put(0x1c,cbcr2); put(0x20,cbcr)
    put(0x24,(16*half_w*aligned_h*3//2)//256); put(0x28,wmb*3); put(0x2c,inter//256-wmb*3-2*len(slices))
    chroma=pp['chroma_qp_index_offset']; qp=pp['pic_init_qp_minus26']
    word=(sp['direct_8x8_inference_flag']<<1)|(pp['weighted_pred_flag']<<2)|(pp['constrained_intra_pred_flag']<<3)|16|\
        (sp['log2_max_frame_num_minus4']<<8)|(1<<12)|(sp['pic_order_cnt_type']<<14)|((qp&63)<<16)|((chroma&31)<<22)|((chroma&31)<<27)
    put(0x30,word); put(0x34,pp['weighted_bipred_idc']); b[0x140:0x220]=bytes([16])*224
    need(out.read_bytes()==bytes(b),'block differs from FFmpeg-derived expected bytes')
    run('build-mesa',['xcrun','clang','-std=gnu11','-dynamiclib',ref,'-o',a.out/'mesa.dylib'],a.out)
    lib=ctypes.CDLL(str((a.out/'mesa.dylib').resolve())); fn=lib.mesa_vp_reference
    fn.argtypes=[ctypes.POINTER(ctypes.c_uint32),ctypes.POINTER(ctypes.c_uint8),ctypes.POINTER(ctypes.c_uint8),ctypes.POINTER(ctypes.c_uint32)]
    fn.restype=ctypes.c_uint32; x=(ctypes.c_uint32*256)(); scale=(ctypes.c_uint8*224)(*([16]*224))
    aligned=(ctypes.c_uint32*189)(); raw=ctypes.cast(aligned,ctypes.POINTER(ctypes.c_uint8)); after=ctypes.c_uint32()
    x[0]=w; x[1]=h; x[2]=len(slices); x[3]=sp['max_num_ref_frames']; x[4]=0; x[5]=0
    x[6]=(sp['direct_8x8_inference_flag']<<1)|(pp['weighted_pred_flag']<<2)|(pp['constrained_intra_pred_flag']<<3)|16
    x[7]=sp['log2_max_frame_num_minus4']; x[8]=sp['pic_order_cnt_type']; x[9]=qp&0xffffffff
    x[10]=chroma&0xffffffff; x[11]=chroma&0xffffffff; x[12]=pp['weighted_bipred_idc']
    caps=fn(x,scale,raw,ctypes.byref(after))
    need(caps==0x1113 and after.value==6 and bytes(raw[:756])==out.read_bytes(),'Mesa IDR block differs')
    need({n:sha(HERE/n) for n in NAMES}==before and sha(ref)==vp['generated_reference_sha256'],'inputs changed')
    result={'status':'PASS_REAL_IDR_VP_CPU','frames_validated':1,'slice_headers':2,'other_p_frames_refused':5,
        'block_bytes':756,'block_sha256':sha(out),'ffmpeg_trace_sha256':sha(a.reference/'trace.txt'),
        'fixture_sha256':EXPECTED['frame-000.avcc'],'baseline_receipt_sha256':sha(a.baseline/'validation.json'),
        'mesa_receipt_sha256':sha(a.vp_baseline/'validation.json'),'mesa_generated_reference_sha256':sha(ref),
        'source_sha256':before,'ffmpeg_derived_bytes_match':True,'mesa_helper_bytes_match':True,
        'complete_h264_validation':False,'hardware_video_execution_proved':False,'system_modified':False}
    (a.out/'validation.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,sort_keys=True))

if __name__=='__main__': main()
