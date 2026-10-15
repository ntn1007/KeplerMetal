#!/usr/bin/env python3
"""Build a public-native thread-limit observer from source, without GPU use."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);(out/'assets').mkdir();old=ROOT/'results/pipeline-contract-reception-client-build-20261015-02';shutil.copytree(old/'runtime',out/'runtime');shutil.copyfile(ROOT/'tools/native_thread_limit_probe.mm',out/'native_thread_limit_probe.mm')
source='#include <metal_stdlib>\nusing namespace metal;\n'
for n in [0,32,64,128,256,1024]:
 attr=f'[[max_total_threads_per_threadgroup({n})]] 'if n else''
 source+=attr+f'kernel void limit_{n if n else "auto"}(device uint *out [[buffer(0)]],uint i [[thread_position_in_grid]]) {{ out[i]=i*1664525u+1013904223u; }}\n'
(out/'limits.metal').write_text(source);commands=[]
for label,cmd in [('metal',['xcrun','metal','-std=macos-metal2.1','-c',out/'limits.metal','-o',out/'limits.air']),('metallib',['xcrun','metallib',out/'limits.air','-o',out/'assets/limits.metallib']),('host',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc',out/'native_thread_limit_probe.mm','-framework','Metal','-framework','Foundation','-o',out/'application'])]:
 cmd=list(map(str,cmd));r=subprocess.run(cmd,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'argv':cmd,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert not r.returncode,r.stderr[-2000:]
sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest();(out/'inputs.json').write_text(json.dumps({'source_hashes':{n:sha(out/n)for n in ['native_thread_limit_probe.mm','limits.metal']},'assets_SHA256':{'limits.metallib':sha(out/'assets/limits.metallib')},'runtime_SHA256':{p.name:sha(p)for p in(out/'runtime').iterdir()if p.is_file()},'executable_SHA256':sha(out/'application'),'GPU_execution':False,'source_generator_SHA256':sha(Path(__file__)),'no_experimental_runtime':True},indent=2)+'\n');print('PASS build',out)
