#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare relative CPU layout calculations to selected Mesa helpers."""
import argparse
import json
import subprocess
import tarfile
from pathlib import Path
from validate import ARCHIVE_SHA, need, sha

HERE = Path(__file__).resolve().parent
FILES = {
 'src/gallium/drivers/nouveau/nouveau_vp3_video.h':'86d97313e8ae883186f1c389a67ebcb69ebe4e5089d55d094fac5ec21acb80bc',
 'src/gallium/drivers/nouveau/nvc0/nvc0_video.c':'2c1662f23fb1afe0fd76c758e4779eee0e0ede8562938f7479e45dd3bec118a6',
}


def reference(header, source):
    notice = header[:header.index('#include "nouveau_winsys.h"')]
    basic = header[header.index('static inline uint32_t nouveau_vp3_video_align'):header.index('static inline uint64_t\nnouveau_vp3_video_addr')]
    layout = header[header.index('static inline void\nnouveau_vp3_ycbcr_offsets'):header.index('struct pipe_video_buffer *\nnouveau_vp3_video_buffer_create')]
    statements = [
      'unsigned inter_size = align(templ->width * templ->height * 2, 4 << 20);',
      'dec->tmp_stride = 16 * mb_half(templ->width) * nouveau_vp3_video_align(templ->height) * 3 / 2;',
      'tmp_size = dec->tmp_stride * (templ->max_references + 1);',
      'dec->ref_stride = mb(templ->width)*16 * (mb_half(templ->height)*32 + nouveau_vp3_video_align(templ->height)/2);',
    ]
    need(all(x in source for x in statements) and '#define SLICE_SIZE 0x200' in header and
         '#define NOUVEAU_VP3_DEBUG_FENCE 0' in header and '# define NOUVEAU_VP3_VIDEO_QDEPTH 2' in header and
         '0, 1 << 20, &cfg, &dec->bsp_bo[i]' in source and
         '&cfg, &dec->inter_bo[0]' in source and '&dec->inter_bo[1]' in source and
         'dec->ref_stride * (templ->max_references+2) + tmp_size' in source, 'Mesa statements differ')
    return notice + r'''#include <assert.h>
#include <stdint.h>
#define SLICE_SIZE 0x200
#define PIPE_VIDEO_FORMAT_MPEG12 1
#define debug_printf(...) ((void)0)
struct bo { uint64_t size; };
struct template_data { uint32_t width, height, max_references, profile; };
struct nouveau_vp3_decoder { struct template_data base; struct bo *inter_bo[1]; uint32_t tmp_stride, ref_stride; };
static uint32_t u_reduce_video_profile(uint32_t p) { return p; }
/* Independent power-of-two alignment helper for the selected Mesa statement. */
static uint32_t align(uint32_t x, uint32_t a) { return (x + a - 1) & ~(a - 1); }
''' + basic + layout + r'''
void mesa_reference_layout(uint32_t w, uint32_t h, uint32_t refs, uint32_t slices, uint64_t *out) {
  struct template_data data = {w, h, refs, 2}, *templ = &data;
  struct nouveau_vp3_decoder d = {0}, *dec = &d;
  struct bo intermediate = {0}; uint32_t tmp_size = 0;
  d.base = data; d.inter_bo[0] = &intermediate;
''' + '\n'.join('  '+x for x in statements) + r'''
  intermediate.size = inter_size;
  uint32_t y2, cbcr, cbcr2, slice, bucket, ring;
  nouveau_vp3_ycbcr_offsets(dec, &y2, &cbcr, &cbcr2);
  nouveau_vp3_inter_sizes(dec, slices, &slice, &bucket, &ring);
  uint64_t tmp_offset = (uint64_t)dec->ref_stride * (refs + 2);
  uint64_t reference_bytes = tmp_offset + tmp_size;
  out[0]=dec->ref_stride; out[1]=reference_bytes; out[2]=dec->tmp_stride; out[3]=tmp_offset;
  out[4]=inter_size; out[5]=reference_bytes + 2*(uint64_t)inter_size + 2*1024*1024;
  out[6]=(uint64_t)y2*256; out[7]=(uint64_t)cbcr*256; out[8]=(uint64_t)cbcr2*256;
  out[9]=slice; out[10]=bucket; out[11]=ring;
}
'''


def run(label, args, out):
    p = subprocess.run(list(map(str,args)), capture_output=True, timeout=120)
    (out/(label+'.stdout')).write_bytes(p.stdout); (out/(label+'.stderr')).write_bytes(p.stderr)
    need(p.returncode == 0, label + ' failed; inspect stderr')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('archive','tree','out'): p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args(); need(not a.out.exists() and a.out.parent.is_dir(), 'fresh output required')
    need(sha(a.archive)==ARCHIVE_SHA, 'archive differs')
    with tarfile.open(a.archive,'r:xz') as archive:
        for name,digest in FILES.items():
            local=a.tree/name; member=archive.extractfile('mesa-26.2.4/'+name)
            need(sha(local)==digest and member is not None and member.read()==local.read_bytes(), 'Mesa member differs')
    header=(a.tree/next(iter(FILES))).read_text()
    source=(a.tree/list(FILES)[1]).read_text()
    a.out.mkdir(); ref=a.out/'mesa-layout-reference.private.c'; ref.write_text(reference(header,source))
    flags=['-O1','-g','-fsanitize=undefined','-fno-omit-frame-pointer']
    run('compiler-version',['xcrun','clang','--version'],a.out)
    run('build-reference',['xcrun','clang','-std=gnu11',*flags,'-c',ref,'-o',a.out/'reference.o'],a.out)
    run('build-test',['xcrun','clang++','-std=c++17','-Wall','-Wextra','-Werror',*flags,
        HERE/'VideoLayout.cpp',HERE/'compare_layout.cpp',a.out/'reference.o','-o',a.out/'test'],a.out)
    run('test',[a.out/'test'],a.out)
    need((a.out/'test.stdout').read_text().startswith('PASS: 4096 Mesa layouts'), 'test receipt differs')
    receipt={'status':'PASS_MESA_RELATIVE_LAYOUTS_CPU','cases':4096,'compared_values':4096*12,
        'mesa_archive_sha256':ARCHIVE_SHA,'mesa_source_sha256':FILES,
        'source_sha256':{n:sha(HERE/n) for n in ('VideoLayout.h','VideoLayout.cpp','compare_layout.cpp','validate_layout.py')},
        'mesa_offset_helpers_executed_on_cpu':True,'mesa_alignment_helper_independently_modeled':True,
        'gpu_allocation_or_submission':False,'hardware_video_execution_proved':False,'system_modified':False}
    (a.out/'validation.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(json.dumps(receipt,sort_keys=True))


if __name__=='__main__': main()
