#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare the exact live-copy experiment offline; no GPU dispatch."""
import argparse
import hashlib
import json
import shutil
import struct
import subprocess
from pathlib import Path

BRIDGE=Path(__file__).resolve().parents[2]
EXPERIMENT=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def need(value, message):
    if not value:raise ValueError(message)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lab',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();lab=args.lab.resolve();out=args.out.resolve()
    out.relative_to(lab/'results')
    need(not out.exists() and out.parent.is_dir(),'fresh output required')
    fixture=lab/'results/cas-dynamic-overlay-20261028-01/results'
    shader=fixture/'dynamic-checked-preflight/test.metal'
    library=fixture/'dynamic-checked-preflight/test.metallib'
    code=fixture/'dynamic-checked-diagnosis/native.sass'
    expected={'shader':'bec093358afd753de23e9722a01d1919732c66dd9bcd9ea47c6dd140d1b04ccb',
              'library':'17cd653eb49ab7749f6013145e71292d51ce467f2a094451e6f1fc9192a31632',
              'code':'f16bf16da56d5dc060429f6886d2e1d80eafa0a960f48b7d776a3234fb6bcb41'}
    for name,path in [('shader',shader),('library',library),('code',code)]:
        need(sha(path)==expected[name],name+' profile differs')
    need(sha(EXPERIMENT/'checked.metal')==expected['shader'],'public shader differs')
    assembler=lab/'results/native-cas-repaired/envyas'
    decoder=lab/'build/envydis-only/envydis/envydis'
    need(sha(assembler)=='1f023d5e1f0a5afc3a04510e264159923dac3182139e03c0a67600b9b1d4428e',
         'assembler differs')
    need(sha(decoder)=='1c8730a9a4861f374c58407bff31d7ccb47a57eb23f9f82c6b3ea3deb079be0f',
         'decoder differs')
    out.mkdir();source=out/'src';source.mkdir()
    for path in (BRIDGE/'src').iterdir():
        if path.suffix in ('.h','.inc'):shutil.copyfile(path,source/path.name)
    shutil.copyfile(BRIDGE/'src/KeplerNativeCAS.mm',out/'import.mm')
    shutil.copyfile(BRIDGE/'tools/air_cas_probe.mm',out/'probe.mm')
    shutil.copyfile(EXPERIMENT/'wrapper.mm',out/'wrapper.mm')
    shutil.copyfile(library,out/'test.metallib');shutil.copyfile(code,out/'original.sass')
    (out/'repair.easm').write_text('''.section #code 0;
.skip 0x530;
long bra #repair_stub;
.skip 0x88;
sched 0x20 0x2f 0x2f 0x20 0x20 0x20 0x20;
repair_stub:
long mov b32 $r1 c2[0x0];
long mov b32 $r0 $r5;
long bra 0x538;
long nop;
long nop;
long nop;
long nop;
''')
    commands=[['clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc',
               '-DPINNED_NATIVE_CAS_IMPORT','-DCOMPILED_METALLIB_CAS_IMPORT',
               '-I',str(source),str(out/'probe.mm'),str(out/'import.mm'),str(out/'wrapper.mm'),
               '-framework','Metal','-framework','Foundation','-o',str(out/'probe')],
              [str(assembler),'-m','gf100','-V','gk104','-i','-o',str(out/'assembled.bin'),str(out/'repair.easm')]]
    for index,command in enumerate(commands):
        result=subprocess.run(command,capture_output=True,timeout=120)
        (out/('build-%d.stdout'%index)).write_bytes(result.stdout)
        (out/('build-%d.stderr'%index)).write_bytes(result.stderr)
        need(result.returncode==0,'build failed; see build-%d.stderr'%index)
    original=(out/'original.sass').read_bytes();assembled=(out/'assembled.bin').read_bytes()
    need(len(original)==0x5c0 and len(assembled)==0x600 and
         original[0x530:0x538]==assembled[0x5c8:0x5d0] and
         struct.unpack_from('<Q',assembled,0x5d0)[0]==0x2800000014001de4,'assembly differs')
    repaired=bytearray(original+assembled[0x5c0:]);repaired[0x530:0x538]=assembled[0x530:0x538]
    trampoline=bytearray(repaired);struct.pack_into('<Q',trampoline,0x5d0,0x4000000000001de4)
    wrong=bytearray(original);wrong[0]^=1
    for name,data in [('repaired',repaired),('trampoline',trampoline),('wrong-original',wrong)]:
        (out/(name+'.sass')).write_bytes(data)
    expected_repair={'repaired':'a193a1c62851ff483bcb3ab7fda86e9646108e36f1552f80a879616e7017e58f',
                     'trampoline':'5be52280903744eabbc4f2ca40f1560091b6c96f5ea12f73bd5b4b769018d2cc'}
    for name,digest in expected_repair.items():need(sha(out/(name+'.sass'))==digest,name+' mismatch')
    result=subprocess.run([str(decoder),'-m','gf100','-V','gk104','-i','-n',str(out/'repaired.sass')],
                          capture_output=True,timeout=30)
    need(result.returncode==0,'decoder failed');listing=result.stdout.decode()
    for off,text in [(0x530,'bra 0x5c8'),(0x5c8,'mov b32 $r1 c2[0x0]'),
                     (0x5d0,'mov b32 $r0 $r5'),(0x5d8,'bra 0x538')]:
        need(any(line.startswith('%08x:'%off) and line.endswith(text) for line in listing.splitlines()),'decoder mismatch')
    (out/'repaired.asm').write_text(listing)
    inputs={str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file()}
    (out/'build.json').write_text(json.dumps({'source_files_and_outputs_SHA256':inputs,
        'GPU_dispatch':False,'assembler_SHA256':sha(assembler),'decoder_SHA256':sha(decoder)},indent=2)+'\n')
    print(json.dumps({'status':'PREPARED','GPU_dispatch':False,'probe_SHA256':sha(out/'probe')}))


if __name__=='__main__':main()
