#!/usr/bin/env python3
"""Build two exact bounded CB0 witness programs offline; no GPU dispatch."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from run_repair import PINS,SYSTEM

HERE=Path(__file__).resolve().parent
BRIDGE=HERE.parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,reason):
    if not ok:raise ValueError(reason)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('lab','base','capture','out'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();lab=a.lab.resolve();base=a.base.resolve();capture=a.capture.resolve();out=a.out.resolve()
    for item in (base,capture,out):item.relative_to(lab/'results')
    need(not out.exists() and out.parent.is_dir(),'fresh output required')
    manifest=json.loads((base/'build.json').read_text())
    for name,digest in manifest['files_SHA256'].items():need(sha(base/name)==digest,'base changed: '+name)
    for name,digest in PINS.items():need(sha(base/name)==digest,'input pin differs: '+name)
    need(sha(capture/'native.metadata')=='f99b8ca94aec90088ba8aee80c42b9e242a7829a81c3fedbf34b2312b08bacbe' and
         sha(base/'import.mm')==sha(BRIDGE/'src/KeplerNativeCAS.mm') and
         sha(base/'src/KeplerConditionalAux.h')==sha(BRIDGE/'src/KeplerConditionalAux.h') and
         sha(base/'src/KeplerNativeCASAdapter.inc')==sha(BRIDGE/'src/KeplerNativeCASAdapter.inc'), 'source or metadata differs')
    need({path:sha(path) for path in SYSTEM}==SYSTEM,'system profile differs')
    assembler=lab/'results/native-cas-repaired/envyas';decoder=lab/'build/envydis-only/envydis/envydis'
    need(sha(assembler)=='1f023d5e1f0a5afc3a04510e264159923dac3182139e03c0a67600b9b1d4428e' and
         sha(decoder)=='1c8730a9a4861f374c58407bff31d7ccb47a57eb23f9f82c6b3ea3deb079be0f','tools differ')
    out.mkdir();shutil.copytree(base/'src',out/'src')
    for name in ('shader.metallib','original.sass'):shutil.copyfile(base/name,out/name)
    shutil.copyfile(capture/'native.metadata',out/'native.metadata')
    shutil.copyfile(base/'import.mm',out/'KeplerNativeCAS.mm')
    for name in ('cb0_readback_host.mm','cb0_readback_import.mm'):shutil.copyfile(HERE/name,out/name)
    orig=(out/'original.sass').read_bytes();need(len(orig)==0x540,'original length differs')
    variants={'control':('mov b32 $r4 0x111','mov b32 $r5 0x222','mov b32 $r6 0x333'),
              'cb0':('mov b32 $r4 c0[0x0]','mov b32 $r5 c0[0x4]','mov b32 $r6 c0[0x8]')}
    for name,ops in variants.items():
        asm=''' .section #code 0;
.skip 0x528;
long bra #witness;
.skip 0x10;
sched 0x20 0x2f 0x2f 0x20 0x20 0x20 0x20;
witness:
'''+''.join('long '+op+';\n' for op in ops)+'''long st b128 wb g[$r0d] $r4q;
long bra 0x530;
long nop;
long nop;
'''
        source=out/(name+'.easm');source.write_text(asm)
        assembled=out/(name+'.assembled');r=subprocess.run([str(assembler),'-m','gf100','-V','gk104','-i','-o',str(assembled),str(source)],capture_output=True,timeout=30)
        (out/(name+'.assemble.stderr')).write_bytes(r.stderr);need(r.returncode==0,'assembly failed: '+name)
        raw=assembled.read_bytes();need(len(raw)==0x580 and raw[0x560:0x568]==orig[0x528:0x530], 'original store not preserved')
        patched=bytearray(orig+raw[len(orig):]);patched[0x528:0x530]=raw[0x528:0x530]
        need([i for i in range(0,len(orig),8) if orig[i:i+8]!=patched[i:i+8]]==[0x528], 'unexpected original modification')
        target=out/(name+'.sass');target.write_bytes(patched)
        dis=subprocess.run([str(decoder),'-m','gf100','-V','gk104','-i','-n',str(target)],capture_output=True,timeout=30)
        need(dis.returncode==0,'decode failed');listing=dis.stdout.decode();(out/(name+'.asm')).write_text(listing)
        for offset,op in [(0x528,'bra 0x548'),(0x548,ops[0]),(0x550,ops[1]),(0x558,ops[2]),
                          (0x560,'st b128 wb g[$r0d] $r4q'),(0x568,'bra 0x530')]:
            need(any(x.startswith('%08x:'%offset) and x.endswith(op) for x in listing.splitlines()),'decoded witness differs: '+name)
    cmd=['clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-I',str(out/'src'),'-I',str(out),
         str(out/'cb0_readback_host.mm'),str(out/'cb0_readback_import.mm'),'-framework','Metal','-framework','Foundation','-o',str(out/'host')]
    r=subprocess.run(cmd,capture_output=True,timeout=120);(out/'build.stderr').write_bytes(r.stderr);need(r.returncode==0,'host build failed')
    files={str(f.relative_to(out)):sha(f) for f in out.rglob('*') if f.is_file()}
    (out/'build.json').write_text(json.dumps({'files_SHA256':files,'GPU_dispatch':False,'assembler_sha256':sha(assembler),
         'decoder_sha256':sha(decoder),'system':SYSTEM},indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':'PREPARED','GPU_dispatch':False,'host_sha256':sha(out/'host'),
                      'control_sha256':sha(out/'control.sass'),'cb0_sha256':sha(out/'cb0.sass')}))

if __name__=='__main__':main()
