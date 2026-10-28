#!/usr/bin/env python3
"""Build one bounded indirect-branch witness offline; no GPU dispatch."""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from run_repair import PINS,SYSTEM

HERE=Path(__file__).resolve().parent
BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'tools'))
from recognize_native_cas import verify_decoder
from trace_native_cas_flow import instructions_from_listing

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,reason):
    if not ok:raise ValueError(reason)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('lab','base','analysis','out'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();lab=a.lab.resolve();base=a.base.resolve();analysis=a.analysis.resolve();out=a.out.resolve()
    for x in (base,analysis,out):x.relative_to(lab/'results')
    need(not out.exists() and out.parent.is_dir(),'fresh output required')
    m=json.loads((base/'build.json').read_text())
    for name,digest in m['files_SHA256'].items():need(sha(base/name)==digest,'base differs: '+name)
    need(sha(base/'shader.metallib')==PINS['shader.metallib'] and sha(base/'original.sass')==PINS['original.sass'] and
         sha(base/'native.metadata')=='f99b8ca94aec90088ba8aee80c42b9e242a7829a81c3fedbf34b2312b08bacbe' and
         sha(base/'KeplerNativeCAS.mm')==sha(BRIDGE/'src/KeplerNativeCAS.mm') and
         sha(base/'src/KeplerConditionalAux.h')==sha(BRIDGE/'src/KeplerConditionalAux.h') and
         sha(base/'src/KeplerNativeCASAdapter.inc')==sha(BRIDGE/'src/KeplerNativeCASAdapter.inc'),'source or capture differs')
    need({path:sha(path) for path in SYSTEM}==SYSTEM,'system profile differs')
    assembler=lab/'results/native-cas-repaired/envyas';decoder=lab/'build/envydis-only/envydis/envydis'
    need(sha(assembler)=='1f023d5e1f0a5afc3a04510e264159923dac3182139e03c0a67600b9b1d4428e' and
         sha(decoder)=='1c8730a9a4861f374c58407bff31d7ccb47a57eb23f9f82c6b3ea3deb079be0f','tools differ')
    original=(base/'original.sass').read_bytes();listing=(analysis/'native.asm').read_text()
    need(len(original)==0x540 and verify_decoder(original,listing,decoder),'original decoder differs')
    ins=instructions_from_listing(original,listing);ops=dict(ins)
    local=[(off,op) for off,op in ins if re.search(r'\bl\[',op)]
    need(local==[(0x148,'st u8 wb l[0x2] $r0'),(0x388,'st u8 wb l[0x0] $r0'),
                 (0x520,'st u8 wb l[0x1] $r3')] and ops[0x290]=='bra $r1 0x0' and
         ops[0x528]=='st b128 wb g[$r0d] $r4q','original local-use or insertion profile differs')
    out.mkdir();shutil.copytree(base/'src',out/'src')
    for name in ('shader.metallib','original.sass','native.metadata','KeplerNativeCAS.mm','cb0_readback_import.mm'):
        shutil.copyfile(base/name,out/name)
    shutil.copyfile(HERE/'branch_witness_host.mm',out/'branch_witness_host.mm')
    asm='''.section #code 0;
.skip 0x290;
long bra #trace;
.skip 0x290;
long bra #save;
.skip 0x10;
sched 0x20 0x2f 0x2f 0x20 0x20 0x20 0x20;
trace:
long st u8 wb l[0x2] $r1;
long bra $r1 0x0;
long nop;
long nop;
long nop;
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
    source=out/'trace.easm';source.write_text(asm);assembled=out/'trace.assembled'
    r=subprocess.run([str(assembler),'-m','gf100','-V','gk104','-i','-o',str(assembled),str(source)],capture_output=True,timeout=30)
    (out/'assemble.stderr').write_bytes(r.stderr);need(r.returncode==0,'assembly failed')
    raw=assembled.read_bytes();need(len(raw)==0x5c0 and raw[0x590:0x598]==original[0x528:0x530],'original store not preserved')
    patched=bytearray(original+raw[len(original):])
    for offset in (0x290,0x528):patched[offset:offset+8]=raw[offset:offset+8]
    need([i for i in range(0,len(original),8) if original[i:i+8]!=patched[i:i+8]]==[0x290,0x528],'unexpected original change')
    (out/'trace.sass').write_bytes(patched)
    dis=subprocess.run([str(decoder),'-m','gf100','-V','gk104','-i','-n',str(out/'trace.sass')],capture_output=True,timeout=30)
    need(dis.returncode==0,'decode failed');text=dis.stdout.decode();(out/'trace.asm').write_text(text)
    for offset,op in [(0x290,'bra 0x548'),(0x528,'bra 0x588'),(0x548,'st u8 wb l[0x2] $r1'),
                      (0x550,'bra $r1 0x0'),(0x588,'ld u8 $r5 ca l[0x2]'),
                      (0x590,'st b128 wb g[$r0d] $r4q'),(0x598,'bra 0x530')]:
        need(any(x.startswith('%08x:'%offset) and x.endswith(op) for x in text.splitlines()),'decoded witness differs')
    cmd=['clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-I',str(out/'src'),'-I',str(out),
         str(out/'branch_witness_host.mm'),str(out/'cb0_readback_import.mm'),'-framework','Metal','-framework','Foundation','-o',str(out/'host')]
    r=subprocess.run(cmd,capture_output=True,timeout=120);(out/'build.stderr').write_bytes(r.stderr);need(r.returncode==0,'host build failed')
    files={str(f.relative_to(out)):sha(f) for f in out.rglob('*') if f.is_file()}
    (out/'build.json').write_text(json.dumps({'files_SHA256':files,'GPU_dispatch':False,'assembler_sha256':sha(assembler),
         'decoder_sha256':sha(decoder),'system':SYSTEM},indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':'PREPARED','GPU_dispatch':False,'trace_sha256':sha(out/'trace.sass'),'host_sha256':sha(out/'host')}))

if __name__=='__main__':main()
