#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare CPU stream staging to selected, locally compiled Mesa helpers."""
import argparse
import hashlib
import json
import subprocess
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
MESA_SHA = '377e44eae4a6196a61b41e9d1361ef896670eab4ace7885cb37ebb34338fd5ea'
ARCHIVE_SHA = 'bce5f7fbebb934373b86c999a064d52fb5065878dc57f287f95346648ec832e9'
FIXTURE_SHA = '12858642f02b0e1d98ddf409dd729a879b6a7a5d3434c860882532ca4f6b40af'
MEMBER = 'mesa-26.2.4/src/gallium/drivers/nouveau/nouveau_vp3_video_bsp.c'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def need(ok, message):
    if not ok:
        raise ValueError(message)


def command(label, argv, out):
    p = subprocess.run(list(map(str, argv)), capture_output=True, timeout=120)
    (out / (label + '.stdout')).write_bytes(p.stdout)
    (out / (label + '.stderr')).write_bytes(p.stderr)
    need(p.returncode == 0, label + ' failed; inspect stderr')


def reference_source(source):
    # Compile the unchanged Mesa begin/next helpers locally. Codec-specific
    # picture parameters and the upstream end() are intentionally not used.
    structure = source[source.index('struct strparm_bsp {'):source.index('struct mpeg12_picparm_bsp {')]
    helpers = source[source.index('static inline struct strparm_bsp *strparm_bsp'):source.index('uint32_t\nnouveau_vp3_bsp_end')]
    notice = source[:source.index('#include "nouveau_vp3_video.h"')]
    return notice + r'''#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#define NOUVEAU_VP3_VIDEO_QDEPTH 1
#define NOUVEAU_VP3_DEBUG_FENCE 0
struct nouveau_bo { char *map; size_t size; };
struct nouveau_vp3_decoder { unsigned fence_seq; struct nouveau_bo *bsp_bo[1]; char *bsp_ptr; };
''' + structure + helpers + r'''
int main(int argc, char **argv) {
  if (argc != 4) return 2;
  FILE *in = fopen(argv[1], "rb"); if (!in || fseek(in, 0, SEEK_END)) return 3;
  long len = ftell(in); if (len < 0 || len > 0xffffef || fseek(in, 0, SEEK_SET)) return 3;
  size_t n = (size_t)len, step = (size_t)strtoul(argv[3], 0, 10); if (!step) return 2;
  char *data = malloc(n ? n : 1); char *map = calloc(1, 0x700 + n + 16);
  if (!data || !map || fread(data, 1, n, in) != n || fclose(in)) return 3;
  struct nouveau_bo bo = {map, 0x700 + n + 16};
  struct nouveau_vp3_decoder dec = {0, {&bo}, 0};
  nouveau_vp3_bsp_begin(&dec);
  for (size_t i = 0; i < n;) {
    unsigned length = (unsigned)((n - i < step) ? n - i : step);
    const void *piece = data + i; nouveau_vp3_bsp_next(&dec, 1, &piece, &length); i += length;
  }
  /* Equivalent H.264 trailer only; do not call Mesa's codec-specific end(). */
  static const unsigned char tail[16] = {0,0,1,11,0,0,0,0,0,0,1,11,0,0,0,0};
  struct strparm_bsp *sp = strparm_bsp(&dec); sp->w0[0] += 16; sp->w1[0] = 1;
  memcpy(dec.bsp_ptr, tail, sizeof(tail));
  FILE *out = fopen(argv[2], "wb"); if (!out) return 5;
  int ok = fwrite(map, 1, bo.size, out) == bo.size && !fclose(out);
  free(data); free(map); return ok ? 0 : 5;
}
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('archive', 'source', 'fixture', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    need(not a.out.exists() and a.out.parent.is_dir(), 'fresh output required')
    need(sha(a.archive) == ARCHIVE_SHA and sha(a.source) == MESA_SHA and
         sha(a.fixture) == FIXTURE_SHA, 'pinned input differs')
    with tarfile.open(a.archive, 'r:xz') as archive:
        member = archive.extractfile(MEMBER)
        need(member is not None and member.read() == a.source.read_bytes(), 'archive member differs')
    a.out.mkdir()
    command('compiler-version', ['xcrun', 'clang', '--version'], a.out)
    ref_source = a.out / 'mesa-reference.private.c'
    ref_source.write_text(reference_source(a.source.read_text()))
    flags = ['-O1', '-g', '-fsanitize=undefined', '-fno-omit-frame-pointer']
    command('build-test', ['xcrun', 'clang++', '-std=c++17', *flags, HERE / 'H264Stream.cpp', HERE / 'test.cpp', '-o', a.out / 'test'], a.out)
    command('build-stage', ['xcrun', 'clang++', '-std=c++17', *flags, HERE / 'H264Stream.cpp', HERE / 'stage_tool.cpp', '-o', a.out / 'stage'], a.out)
    command('build-reference', ['xcrun', 'clang', '-std=gnu11', '-DNDEBUG', *flags, ref_source, '-o', a.out / 'reference'], a.out)
    command('unit', [a.out / 'test'], a.out)
    input_size = a.fixture.stat().st_size
    for step in (1, 3, 7, 64, 4096, input_size):
        target, reference = a.out / ('staged-%d.bin' % step), a.out / ('reference-%d.bin' % step)
        command('stage-%d' % step, [a.out / 'stage', a.fixture, target, step], a.out)
        command('reference-%d' % step, [a.out / 'reference', a.fixture, reference, step], a.out)
        need(target.read_bytes() == reference.read_bytes(), 'Mesa helper comparison differs')
    outputs = [sha(a.out / ('staged-%d.bin' % step)) for step in (1, 3, 7, 64, 4096, input_size)]
    need(len(set(outputs)) == 1, 'chunking changed output')
    receipt = {'status': 'PASS_MESA_CPU_STREAM_STAGING', 'mesa_archive_sha256': ARCHIVE_SHA,
               'mesa_source_sha256': MESA_SHA, 'fixture_sha256': FIXTURE_SHA,
               'fixture_bytes': input_size, 'chunkings': 6, 'output_sha256': outputs[0],
               'source_sha256': {x: sha(HERE / x) for x in ('H264Stream.h', 'H264Stream.cpp', 'test.cpp', 'stage_tool.cpp', 'validate.py')},
               'reference_uses_mesa_begin_and_next': True, 'reference_uses_mesa_end': False,
               'picture_descriptor_implemented': False, 'gpu_transport_implemented': False,
               'hardware_video_execution_proved': False, 'system_modified': False}
    (a.out / 'validation.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
