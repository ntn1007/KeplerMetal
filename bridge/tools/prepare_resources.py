#!/usr/bin/env python3
"""Capture unmodified resource kernels in our process and decode their bindings."""
from pathlib import Path
import subprocess
import json
import struct
import hashlib

root=Path(__file__).resolve().parents[1];out=root/'results/resource-native';out.mkdir(exist_ok=True)
commands=[]
def run(command,label):
    result=subprocess.run(command,cwd=root,capture_output=True,text=True,timeout=60)
    (out/(label+'.stdout')).write_text(result.stdout);(out/(label+'.stderr')).write_text(result.stderr)
    commands.append({'command':command,'label':label,'exit_code':result.returncode})
    (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,result.returncode,flush=True)
    if result.returncode:print(result.stderr[-2500:]);raise SystemExit(result.returncode)
    return result.stdout
run(['xcrun','-sdk','macosx','metal','-std=macos-metal2.4','-c',str(root/'src/resource_carrier.metal'),'-o',str(out/'resource_carrier.air')],'carrier-air')
run(['xcrun','-sdk','macosx','metallib',str(out/'resource_carrier.air'),'-o',str(out/'resource_carrier.metallib')],'carrier-metallib')
run(['clang++','-O1','-std=c++17','-fno-objc-arc',str(root/'tools/compiler_output_trace.mm'),'-framework','Metal','-framework','Foundation','-o',str(root/'build/compiler_output_trace')],'capture-build')
records=[]
for name in ('buffers_a','buffers_b','buffers_rw','image_store'):
    folder=out/name
    run([str(root/'build/compiler_output_trace'),str(out/'resource_carrier.metallib'),str(folder),'compute',name],name+'-capture')
    payload=folder/'program-0.compiler-output.bin';b=payload.read_bytes();offset=8;sections=[]
    for _ in range(32):
        next_,kind,size=struct.unpack_from('<QII',b,offset);entry={'type':hex(kind),'offset':offset,'size':size};sections.append(entry)
        if kind==1:entry['stage']=struct.unpack_from('<I',b,offset+16)[0]
        if kind==0x10004:entry['words']=list(struct.unpack_from('<'+str(size//4)+'I',b,offset+16))
        if kind==0x10005:
            code=b[offset+16:offset+16+size];(folder/'native.sass').write_bytes(code)
            run([str(root/'build/envydis-only/envydis/envydis'),'-m','gf100','-V','gk104','-i','-n',str(folder/'native.sass')],name+'-decode')
        if not next_:break
        offset+=next_
    records.append({'name':name,'version':struct.unpack_from('<I',b)[0],'sha256':hashlib.sha256(b).hexdigest(),'sections':sections})
(out/'binding-captures.json').write_text(json.dumps(records,indent=2)+'\n')
