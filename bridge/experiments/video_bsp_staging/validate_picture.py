#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compile Mesa's unchanged H.264 BSP picture helper as a CPU oracle."""
import argparse
import json
import subprocess
import tarfile
from pathlib import Path

from validate import ARCHIVE_SHA, MEMBER, MESA_SHA, need, sha

HERE = Path(__file__).resolve().parent


def reference_source(source):
    notice = source[:source.index('#include "nouveau_vp3_video.h"')]
    structure = source[source.index('struct h264_picparm_bsp {'):source.index('static uint32_t\nnouveau_vp3_fill_picparm_mpeg12_bsp')]
    helper = source[source.index('static uint32_t\nnouveau_vp3_fill_picparm_h264_bsp'):source.index('static inline struct strparm_bsp *strparm_bsp')]
    return notice + r'''#include <assert.h>
#include <stddef.h>
#include <stdint.h>
#include <string.h>
struct pipe_h264_sps {
  uint8_t log2_max_frame_num_minus4, pic_order_cnt_type, log2_max_pic_order_cnt_lsb_minus4;
  uint8_t delta_pic_order_always_zero_flag, frame_mbs_only_flag, direct_8x8_inference_flag, mb_adaptive_frame_field_flag;
};
struct pipe_h264_pps {
  struct pipe_h264_sps *sps;
  uint8_t entropy_coding_mode_flag, bottom_field_pic_order_in_frame_present_flag, weighted_pred_flag, weighted_bipred_idc;
  int8_t pic_init_qp_minus26;
  uint8_t deblocking_filter_control_present_flag, redundant_pic_cnt_present_flag, transform_8x8_mode_flag;
};
struct pipe_h264_picture_desc {
  struct pipe_h264_pps *pps;
  uint8_t num_ref_idx_l0_active_minus1, num_ref_idx_l1_active_minus1, field_pic_flag, bottom_field_flag;
  uint32_t slice_count;
};
struct nouveau_vp3_decoder { struct { uint32_t width, height; } base; };
static uint32_t mb(uint32_t value) { return (value + 15) >> 4; }
''' + structure + helper + r'''
uint32_t mesa_reference_picture(const uint32_t *x, unsigned char *out) {
  assert(sizeof(struct h264_picparm_bsp) == 124);
  struct pipe_h264_sps s = {0}; struct pipe_h264_pps p = {0};
  struct pipe_h264_picture_desc d = {0}; struct nouveau_vp3_decoder dec = {0};
  dec.base.width=x[0]; dec.base.height=x[1]; d.slice_count=x[2];
  s.log2_max_frame_num_minus4=x[3]; s.pic_order_cnt_type=x[4];
  s.log2_max_pic_order_cnt_lsb_minus4=x[5]; s.delta_pic_order_always_zero_flag=x[6];
  s.frame_mbs_only_flag=x[7]; s.direct_8x8_inference_flag=x[8];
  p.entropy_coding_mode_flag=x[9]; p.bottom_field_pic_order_in_frame_present_flag=x[10];
  d.num_ref_idx_l0_active_minus1=x[11]; d.num_ref_idx_l1_active_minus1=x[12];
  p.weighted_pred_flag=x[13]; p.weighted_bipred_idc=x[14]; p.pic_init_qp_minus26=(int8_t)x[15];
  p.deblocking_filter_control_present_flag=x[16]; p.redundant_pic_cnt_present_flag=x[17];
  p.transform_8x8_mode_flag=x[18]; s.mb_adaptive_frame_field_flag=x[19];
  d.field_pic_flag=x[20]; d.bottom_field_flag=x[21]; p.sps=&s; d.pps=&p;
  return nouveau_vp3_fill_picparm_h264_bsp(&dec, &d, (char*)out);
}
'''


def command(label, argv, out):
    result = subprocess.run(list(map(str, argv)), capture_output=True, timeout=120)
    (out / (label + '.stdout')).write_bytes(result.stdout)
    (out / (label + '.stderr')).write_bytes(result.stderr)
    need(result.returncode == 0, label + ' failed; inspect retained stderr')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('archive', 'source', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    need(not a.out.exists() and a.out.parent.is_dir(), 'fresh output required')
    need(sha(a.archive) == ARCHIVE_SHA and sha(a.source) == MESA_SHA, 'pinned input differs')
    with tarfile.open(a.archive, 'r:xz') as archive:
        member = archive.extractfile(MEMBER)
        need(member is not None and member.read() == a.source.read_bytes(), 'archive member differs')
    a.out.mkdir()
    ref = a.out / 'mesa-picture-reference.private.c'
    ref.write_text(reference_source(a.source.read_text()))
    common = ['-O1', '-g', '-fsanitize=undefined', '-fno-omit-frame-pointer']
    command('compiler-version', ['xcrun', 'clang', '--version'], a.out)
    command('build-reference', ['xcrun', 'clang', '-std=gnu11', *common, '-c', ref, '-o', a.out / 'reference.o'], a.out)
    command('build-compare', ['xcrun', 'clang++', '-std=c++17', '-Wall', '-Wextra', '-Werror', *common,
                              HERE / 'H264Stream.cpp', HERE / 'compare_picture.cpp', a.out / 'reference.o',
                              '-o', a.out / 'compare'], a.out)
    command('compare', [a.out / 'compare'], a.out)
    need((a.out / 'compare.stdout').read_text().startswith('PASS: 4096 Mesa picture blocks'), 'comparison receipt differs')
    receipt = {'status': 'PASS_MESA_H264_BSP_PICTURES_CPU', 'mesa_archive_sha256': ARCHIVE_SHA,
               'mesa_source_sha256': MESA_SHA, 'cases': 4096, 'picture_bytes_per_case': 124,
               'compared_picture_bytes': 4096 * 124, 'source_sha256': {n: sha(HERE / n) for n in
                 ('H264Stream.h', 'H264Stream.cpp', 'compare_picture.cpp', 'validate.py', 'validate_picture.py')},
               'mesa_h264_picture_helper_executed_on_cpu': True, 'watchdog_bit_checked_separately': True,
               'h264_bitstream_parsed': False, 'gpu_transport_implemented': False,
               'hardware_video_execution_proved': False, 'system_modified': False}
    (a.out / 'validation.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
