#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the exact conditional-CAS repair experiment without dispatching GPU work."""
import argparse
import hashlib
import json
import shutil
import struct
import subprocess
from pathlib import Path

EXPERIMENT=Path(__file__).resolve().parent
BRIDGE=EXPERIMENT.parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def need(value,message):
    if not value:raise ValueError(message)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('lab','capture','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();lab=a.lab.resolve();capture=a.capture.resolve();out=a.out.resolve()
    capture.relative_to(lab/'results');out.relative_to(lab/'results')
    need(not out.exists() and out.parent.is_dir(),'fresh output required')
    pins={'input.metallib':'811e53236f858247d59ae1540efb1a74160c0e566522faadd9fa82ad60de8640',
          'native.sass':'83fedb1873bf54ae9975d3f44bd8e8512a9639903afee18d2decef4fbcdd2eb2',
          'native.metadata':'f99b8ca94aec90088ba8aee80c42b9e242a7829a81c3fedbf34b2312b08bacbe'}
    for name,digest in pins.items():need(sha(capture/name)==digest,'capture profile differs: '+name)
    manifest=json.loads((capture/'manifest.json').read_text())
    need(manifest['GPU_reservation']['state']=='terminal' and manifest['exit_code']==0 and
         not manifest['SIGKILL_requested'] and not manifest['authoritative_ps_status'] and
         manifest['library_SHA256']==pins['input.metallib'],'capture receipt differs')
    assembler=lab/'results/native-cas-repaired/envyas';decoder=lab/'build/envydis-only/envydis/envydis'
    need(sha(assembler)=='1f023d5e1f0a5afc3a04510e264159923dac3182139e03c0a67600b9b1d4428e' and
         sha(decoder)=='1c8730a9a4861f374c58407bff31d7ccb47a57eb23f9f82c6b3ea3deb079be0f','tool profile differs')
    driver=Path('/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver')
    air=Path('/System/Library/Extensions/GeForceAIRPlugin.bundle/Contents/MacOS/GeForceAIRPlugin')
    need(sha(driver)=='e240d54a4cd64b7e54fbc15250de82e88451132e1d9f3a4f9879607c8b0e7645' and
         sha(air)=='692af9a05d750ac4eedfe3181feed73cb1214b83454f748b3a845b3a3a6aabac','system profile differs')
    out.mkdir();src=out/'src';src.mkdir()
    for file in (BRIDGE/'src').iterdir():
        if file.suffix in ('.h','.inc'):shutil.copyfile(file,src/file.name)
    shutil.copyfile(BRIDGE/'src/KeplerNativeCAS.mm',out/'import.mm')
    shutil.copyfile(EXPERIMENT/'repair_host.mm',out/'repair_host.mm')
    shutil.copyfile(capture/'input.metallib',out/'shader.metallib')
    shutil.copyfile(capture/'native.sass',out/'original.sass')
    assembly='''.section #code 0;
.skip 0x428;
long bra #repair_stub;
.skip 0x110;
sched 0x20 0x2f 0x2f 0x20 0x20 0x20 0x20;
repair_stub:
long mov b32 $r10 0x80000000;
long mov b32 $r4 $r0;
long bra 0x430;
long nop;
long nop;
long nop;
long nop;
'''
    (out/'repair.easm').write_text(assembly)
    commands=[['clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-I',str(src),
               str(out/'repair_host.mm'),str(out/'import.mm'),'-framework','Metal','-framework','Foundation','-o',str(out/'host')],
              [str(assembler),'-m','gf100','-V','gk104','-i','-o',str(out/'assembled.bin'),str(out/'repair.easm')]]
    for i,command in enumerate(commands):
        r=subprocess.run(command,capture_output=True,timeout=120)
        (out/('build-%d.stdout'%i)).write_bytes(r.stdout);(out/('build-%d.stderr'%i)).write_bytes(r.stderr)
        need(r.returncode==0,'build failed: '+str(i))
    original=(out/'original.sass').read_bytes();assembled=(out/'assembled.bin').read_bytes()
    need(len(original)==0x540 and len(assembled)==0x580 and
         original[0x428:0x430]==assembled[0x548:0x550] and
         struct.unpack_from('<Q',assembled,0x550)[0]==0x2800000000011de4,'assembled instructions differ')
    repaired=bytearray(original+assembled[len(original):]);repaired[0x428:0x430]=assembled[0x428:0x430]
    control=bytearray(repaired);struct.pack_into('<Q',control,0x550,0x4000000000001de4)
    wrong=bytearray(original);wrong[0]^=1
    need([i for i in range(0,len(original),8) if original[i:i+8]!=repaired[i:i+8]]==[0x428] and
         [i for i in range(0,len(repaired),8) if repaired[i:i+8]!=control[i:i+8]]==[0x550],
         'unexpected changed words')
    for name,data in [('repaired',repaired),('trampoline',control),('wrong-original',wrong)]:
        (out/(name+'.sass')).write_bytes(data)
    need(sha(out/'repaired.sass')=='d0dfcbe6cbcdbba8df91289d7eb56f122ba48eeeb91d7c6b294ceaf7c291e1e8' and
         sha(out/'trampoline.sass')=='518a2b787d35d2e54dd8cc8b213f52e5b5c5faa6135599241bbbd74f433bd213',
         'assembled program fingerprint differs')
    decoded=subprocess.run([str(decoder),'-m','gf100','-V','gk104','-i','-n',str(out/'repaired.sass')],capture_output=True,timeout=30)
    need(decoded.returncode==0,'decoder failed');text=decoded.stdout.decode();(out/'repaired.asm').write_text(text)
    for offset,op in [(0x428,'bra 0x548'),(0x548,'mov b32 $r10 0x80000000'),
                      (0x550,'mov b32 $r4 $r0'),(0x558,'bra 0x430')]:
        need(any(x.startswith('%08x:'%offset) and x.endswith(op) for x in text.splitlines()),'decoded instruction differs')
    files={str(f.relative_to(out)):sha(f) for f in out.rglob('*') if f.is_file()}
    (out/'build.json').write_text(json.dumps({'files_SHA256':files,'assembler_SHA256':sha(assembler),
        'decoder_SHA256':sha(decoder),'driver_SHA256':sha(driver),'AIR_plugin_SHA256':sha(air),
        'GPU_dispatch':False},indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':'PREPARED','GPU_dispatch':False,'host_SHA256':sha(out/'host')}))


if __name__=='__main__':main()
