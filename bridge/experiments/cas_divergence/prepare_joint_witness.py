#!/usr/bin/env python3
"""Assemble a profile-pinned joint branch/target witness, without dispatching it."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from run_repair import PINS, SYSTEM

HERE = Path(__file__).resolve().parent
BRIDGE = HERE.parents[1]
sys.path.insert(0, str(BRIDGE / 'tools'))
from recognize_native_cas import verify_decoder
from trace_native_cas_flow import instructions_from_listing

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def need(ok, reason):
    if not ok:
        raise ValueError(reason)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('lab', 'base', 'analysis', 'out'):
        p.add_argument('--' + key, type=Path, required=True)
    a = p.parse_args()
    lab, base, analysis, out = (getattr(a, key).resolve() for key in ('lab', 'base', 'analysis', 'out'))
    for path in (base, analysis, out):
        path.relative_to(lab / 'results')
    need(not out.exists() and out.parent.is_dir(), 'fresh output required')
    manifest = json.loads((base / 'build.json').read_text())
    for name, digest in manifest['files_SHA256'].items():
        need(sha(base / name) == digest, 'base changed: ' + name)
    need(sha(base / 'shader.metallib') == PINS['shader.metallib'] and
         sha(base / 'original.sass') == PINS['original.sass'] and
         sha(base / 'native.metadata') == 'f99b8ca94aec90088ba8aee80c42b9e242a7829a81c3fedbf34b2312b08bacbe' and
         sha(base / 'KeplerNativeCAS.mm') == sha(BRIDGE / 'src/KeplerNativeCAS.mm') and
         sha(base / 'src/KeplerConditionalAux.h') == sha(BRIDGE / 'src/KeplerConditionalAux.h') and
         sha(base / 'src/KeplerNativeCASAdapter.inc') == sha(BRIDGE / 'src/KeplerNativeCASAdapter.inc'), 'profile changed')
    need({path: sha(path) for path in SYSTEM} == SYSTEM, 'system profile changed')
    assembler = lab / 'results/native-cas-repaired/envyas'
    decoder = lab / 'build/envydis-only/envydis/envydis'
    need(sha(assembler) == '1f023d5e1f0a5afc3a04510e264159923dac3182139e03c0a67600b9b1d4428e' and
         sha(decoder) == '1c8730a9a4861f374c58407bff31d7ccb47a57eb23f9f82c6b3ea3deb079be0f', 'tools changed')
    original = (base / 'original.sass').read_bytes()
    listing = (analysis / 'native.asm').read_text()
    need(len(original) == 0x540 and verify_decoder(original, listing, decoder), 'native decode differs')
    instructions = instructions_from_listing(original, listing)
    ops = dict(instructions)
    local = [(offset, op) for offset, op in instructions if re.search(r'\bl\[', op)]
    need(local == [(0x148, 'st u8 wb l[0x2] $r0'), (0x388, 'st u8 wb l[0x0] $r0'),
                   (0x520, 'st u8 wb l[0x1] $r3')] and
         ops[0x290] == 'bra $r1 0x0' and ops[0x330] == 'mov b32 $r0 c2[0xc]' and
         ops[0x528] == 'st b128 wb g[$r0d] $r4q', 'native insertion profile differs')
    out.mkdir()
    shutil.copytree(base / 'src', out / 'src')
    for name in ('shader.metallib', 'original.sass', 'native.metadata', 'KeplerNativeCAS.mm', 'cb0_readback_import.mm'):
        shutil.copyfile(base / name, out / name)
    shutil.copyfile(HERE / 'branch_witness_host.mm', out / 'branch_witness_host.mm')
    asm = '''.section #code 0;
.skip 0x290;
long bra #branch_trace;
.skip 0x98;
long bra #target_trace;
.skip 0x1f0;
long bra #save;
.skip 0x10;
sched 0x20 0x2f 0x2f 0x20 0x20 0x20 0x20;
branch_trace:
long st u8 wb l[0x2] $r1;
long bra $r1 0x0;
long nop;
long nop;
long nop;
long nop;
long nop;
sched 0x2f 0x2f 0x2f 0x2f 0x20 0x20 0x20;
target_trace:
long ld u8 $r0 ca l[0x2];
long add b32 $r0 $r0 0x1;
long st u8 wb l[0x2] $r0;
long mov b32 $r0 c2[0xc];
long bra 0x338;
long nop;
long nop;
sched 0x20 0x2f 0x2f 0x20 0x20 0x20 0x20;
save:
long ld u8 $r5 ca l[0x2];
long st b128 wb g[$r0d] $r4q;
long bra 0x530;
long nop;
long nop;
long nop;
long nop;
'''
    source = out / 'trace.easm'
    source.write_text(asm)
    assembled = out / 'trace.assembled'
    run = subprocess.run([str(assembler), '-m', 'gf100', '-V', 'gk104', '-i', '-o', str(assembled), str(source)], capture_output=True, timeout=30)
    (out / 'assemble.stderr').write_bytes(run.stderr)
    need(run.returncode == 0, 'assembly failed')
    raw = assembled.read_bytes()
    need(len(raw) == 0x600 and raw[0x5a0:0x5a8] == original[0x330:0x338] and
         raw[0x5d0:0x5d8] == original[0x528:0x530], 'displaced instructions differ')
    patched = bytearray(original + raw[len(original):])
    for offset in (0x290, 0x330, 0x528):
        patched[offset:offset + 8] = raw[offset:offset + 8]
    need([i for i in range(0, len(original), 8) if original[i:i + 8] != patched[i:i + 8]] == [0x290, 0x330, 0x528], 'unexpected native modification')
    (out / 'trace.sass').write_bytes(patched)
    dis = subprocess.run([str(decoder), '-m', 'gf100', '-V', 'gk104', '-i', '-n', str(out / 'trace.sass')], capture_output=True, timeout=30)
    need(dis.returncode == 0, 'decode failed')
    text = dis.stdout.decode()
    (out / 'trace.asm').write_text(text)
    for offset, op in [(0x290, 'bra 0x548'), (0x330, 'bra 0x588'), (0x528, 'bra 0x5c8'),
                       (0x548, 'st u8 wb l[0x2] $r1'), (0x550, 'bra $r1 0x0'),
                       (0x588, 'ld u8 $r0 ca l[0x2]'), (0x590, 'add b32 $r0 $r0 0x1'),
                       (0x598, 'st u8 wb l[0x2] $r0'), (0x5a0, 'mov b32 $r0 c2[0xc]'),
                       (0x5a8, 'bra 0x338'), (0x5c8, 'ld u8 $r5 ca l[0x2]'),
                       (0x5d0, 'st b128 wb g[$r0d] $r4q'), (0x5d8, 'bra 0x530')]:
        need(any(line.startswith('%08x:' % offset) and line.endswith(op) for line in text.splitlines()), 'decoded witness differs at ' + hex(offset))
    cmd = ['clang++', '-arch', 'x86_64', '-O2', '-std=c++17', '-fno-objc-arc', '-I', str(out / 'src'), '-I', str(out),
           str(out / 'branch_witness_host.mm'), str(out / 'cb0_readback_import.mm'), '-framework', 'Metal', '-framework', 'Foundation', '-o', str(out / 'host')]
    run = subprocess.run(cmd, capture_output=True, timeout=120)
    (out / 'build.stderr').write_bytes(run.stderr)
    need(run.returncode == 0, 'host build failed')
    files = {str(f.relative_to(out)): sha(f) for f in out.rglob('*') if f.is_file()}
    (out / 'build.json').write_text(json.dumps({'files_SHA256': files, 'GPU_dispatch': False, 'assembler_sha256': sha(assembler),
        'decoder_sha256': sha(decoder), 'system': SYSTEM}, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'status': 'PREPARED', 'GPU_dispatch': False, 'trace_sha256': sha(out / 'trace.sass'), 'host_sha256': sha(out / 'host')}))

if __name__ == '__main__':
    main()
