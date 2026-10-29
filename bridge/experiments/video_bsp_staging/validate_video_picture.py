#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare the CPU VP block and proposed state with pinned Mesa helpers."""
import argparse
import json
import subprocess
import tarfile
from pathlib import Path
from validate import ARCHIVE_SHA, need, sha
from validate_layout import FILES

HERE = Path(__file__).resolve().parent
VP = 'src/gallium/drivers/nouveau/nouveau_vp3_video_vp.c'
VP_SHA = '3c44d8153d08764aacf012cd46186819a120979c34f87adb0a3bee592d898c9f'
HEADER = 'src/gallium/drivers/nouveau/nouveau_vp3_video.h'

def reference(header, source):
    notice = source[:source.index('#include "nouveau_vp3_video.h"')]
    basic = header[header.index('static inline uint32_t nouveau_vp3_video_align'):header.index('static inline uint64_t\nnouveau_vp3_video_addr')]
    layout = header[header.index('static inline void\nnouveau_vp3_ycbcr_offsets'):header.index('struct pipe_video_buffer *\nnouveau_vp3_video_buffer_create')]
    structure = source[source.index('struct h264_picparm_vp {'):source.index('static void\nnouveau_vp3_handle_references')]
    helpers = source[source.index('static uint32_t\nnouveau_vp3_fill_picparm_h264_vp'):source.index('static uint32_t\nnouveau_vp3_fill_picparm_vc1_vp')]
    return notice + r'''#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
#define SLICE_SIZE 0x200
#define PIPE_VIDEO_FORMAT_MPEG12 1
#define debug_printf(...) ((void)0)
struct bo { uint64_t size; };
struct nouveau_vp3_video_buffer { unsigned valid_ref; };
struct pipe_h264_sps { unsigned mb_adaptive_frame_field_flag, direct_8x8_inference_flag, log2_max_frame_num_minus4, pic_order_cnt_type; };
struct pipe_h264_pps { struct pipe_h264_sps *sps; unsigned weighted_pred_flag, constrained_intra_pred_flag, weighted_bipred_idc; int pic_init_qp_minus26, chroma_qp_index_offset, second_chroma_qp_index_offset; uint8_t ScalingList4x4[6][16], ScalingList8x8[2][64]; };
struct pipe_h264_picture_desc {
 struct pipe_h264_pps *pps; unsigned is_reference, frame_num, slice_count, field_pic_flag, bottom_field_flag, num_ref_frames;
 struct nouveau_vp3_video_buffer *ref[16]; int32_t field_order_cnt[2], field_order_cnt_list[16][2];
 uint32_t frame_num_list[16]; unsigned top_is_reference[16], bottom_is_reference[16], is_long_term[16];
};
struct nouveau_vp3_decoder {
 struct { uint32_t width,height,max_references,profile; } base;
 struct bo *inter_bo[1]; uint32_t tmp_stride,ref_stride,last_frame_num;
 struct { struct nouveau_vp3_video_buffer *vidbuf; unsigned field_pic_flag,decoded_top,decoded_bottom,decoded_first; } refs[17];
};
static uint32_t u_reduce_video_profile(uint32_t p) { return p; }
''' + basic + layout + structure + helpers + r'''
uint32_t mesa_vp_reference(const uint32_t *x, const uint8_t *scaling, uint8_t *out, uint32_t *after) {
 assert(sizeof(struct h264_picparm_vp)==756);
 struct pipe_h264_sps s={0}; struct pipe_h264_pps p={0}; struct pipe_h264_picture_desc d={0};
 struct nouveau_vp3_decoder dec={0}; struct bo intermediate={0};
 struct nouveau_vp3_video_buffer buffers[17]={0}, *refs[16]={0}; unsigned is_ref=0;
 dec.base.width=x[0]; dec.base.height=x[1]; dec.base.max_references=x[3]; dec.base.profile=2;
 intermediate.size=((uint64_t)x[0]*x[1]*2+((4u<<20)-1))&~((uint64_t)(4u<<20)-1);
 dec.inter_bo[0]=&intermediate;
 dec.tmp_stride=16*mb_half(x[0])*nouveau_vp3_video_align(x[1])*3/2;
 dec.ref_stride=mb(x[0])*16*(mb_half(x[1])*32+nouveau_vp3_video_align(x[1])/2);
 for(unsigned i=0;i<17;i++) { buffers[i].valid_ref=i; dec.refs[i].vidbuf=&buffers[i];
   dec.refs[i].field_pic_flag=!!(x[32+i]&1); dec.refs[i].decoded_top=!!(x[32+i]&2);
   dec.refs[i].decoded_bottom=!!(x[32+i]&4); dec.refs[i].decoded_first=!!(x[32+i]&8); }
 d.pps=&p; p.sps=&s; d.slice_count=x[2]; d.num_ref_frames=x[4];
 s.mb_adaptive_frame_field_flag=!!(x[6]&1); s.direct_8x8_inference_flag=!!(x[6]&2);
 p.weighted_pred_flag=!!(x[6]&4); p.constrained_intra_pred_flag=!!(x[6]&8);
 d.is_reference=!!(x[6]&16); d.field_pic_flag=!!(x[6]&32); d.bottom_field_flag=!!(x[6]&64);
 s.log2_max_frame_num_minus4=x[7]; s.pic_order_cnt_type=x[8]; p.pic_init_qp_minus26=(int32_t)x[9];
 p.chroma_qp_index_offset=(int32_t)x[10]; p.second_chroma_qp_index_offset=(int32_t)x[11];
 p.weighted_bipred_idc=x[12]; d.frame_num=x[13]; d.field_order_cnt[0]=(int32_t)x[14]; d.field_order_cnt[1]=(int32_t)x[15];
 memcpy(p.ScalingList4x4,scaling,96); memcpy(p.ScalingList8x8,scaling+96,128);
 for(unsigned i=0;i<x[4];i++) { const uint32_t *r=x+64+5*i; d.ref[i]=&buffers[r[0]];
   d.top_is_reference[i]=!!(r[1]&1); d.bottom_is_reference[i]=!!(r[1]&2); d.is_long_term[i]=!!(r[1]&4);
   d.field_order_cnt_list[i][0]=(int32_t)r[2]; d.field_order_cnt_list[i][1]=(int32_t)r[3]; d.frame_num_list[i]=r[4]; }
 uint32_t caps=nouveau_vp3_fill_picparm_h264_vp(&dec,&d,refs,&is_ref,(char*)out);
 assert(is_ref==d.is_reference);
 nouveau_vp3_fill_picparm_h264_vp_refs(&dec,&d,refs,&buffers[x[5]],(char*)out);
 *after=dec.refs[x[5]].field_pic_flag | dec.refs[x[5]].decoded_top<<1 |
    dec.refs[x[5]].decoded_bottom<<2 | dec.refs[x[5]].decoded_first<<3;
 return caps;
}
'''

def run(label,args,out):
    p=subprocess.run(list(map(str,args)),capture_output=True,timeout=120)
    (out/(label+'.stdout')).write_bytes(p.stdout); (out/(label+'.stderr')).write_bytes(p.stderr)
    need(p.returncode==0,label+' failed; inspect retained stderr')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('archive','tree','out'): p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args(); need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required')
    need(sha(a.archive)==ARCHIVE_SHA,'archive differs')
    files={HEADER:FILES[HEADER],VP:VP_SHA}
    with tarfile.open(a.archive,'r:xz') as tar:
        for name,digest in files.items():
            local=a.tree/name; member=tar.extractfile('mesa-26.2.4/'+name)
            need(sha(local)==digest and member is not None and member.read()==local.read_bytes(),'Mesa member differs')
    a.out.mkdir(); ref=a.out/'mesa-vp-reference.private.c'
    ref.write_text(reference((a.tree/HEADER).read_text(),(a.tree/VP).read_text()))
    flags=['-O1','-g','-fsanitize=undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer']
    run('compiler-version',['xcrun','clang','--version'],a.out)
    run('build-reference',['xcrun','clang','-std=gnu11',*flags,'-c',ref,'-o',a.out/'reference.o'],a.out)
    run('build-test',['xcrun','clang++','-std=c++17','-Wall','-Wextra','-Werror',*flags,
        HERE/'VideoLayout.cpp',HERE/'VideoPicture.cpp',HERE/'compare_video_picture.cpp',a.out/'reference.o','-o',a.out/'test'],a.out)
    run('test',[a.out/'test'],a.out)
    need((a.out/'test.stdout').read_text().startswith('PASS: 4096 Mesa VP picture blocks'),'comparison receipt differs')
    need(not (a.out/'test.stderr').read_bytes(),'sanitizer diagnostics found')
    names=('H264Stream.h','VideoLayout.h','VideoLayout.cpp','VideoPicture.h','VideoPicture.cpp',
           'compare_video_picture.cpp','validate.py','validate_layout.py','validate_video_picture.py')
    receipt={'status':'PASS_MESA_VP_BLOCKS_CPU','cases':4096,'bytes_per_case':756,
       'mesa_archive_sha256':ARCHIVE_SHA,'mesa_source_sha256':files,
       'source_sha256':{n:sha(HERE/n) for n in names},'generated_reference_sha256':sha(ref),
       'mesa_vp_helpers_executed_on_cpu':True,
       'inputs_are_synthetic':True,'gpu_transport_implemented':False,'hardware_video_execution_proved':False,'system_modified':False}
    (a.out/'validation.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(json.dumps(receipt,sort_keys=True))

if __name__=='__main__': main()
