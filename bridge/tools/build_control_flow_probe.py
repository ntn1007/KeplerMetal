#!/usr/bin/env python3
"""Generate bounded nested loops and freeze a native reference/constructor observer."""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess, time
ROOT=Path(__file__).resolve().parents[1]
DEPTHS=(0,4,8,16,24,40,64,96)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def source(entry_witness=False):
    lines=['// SPDX-License-Identifier: MIT','#include <metal_stdlib>','using namespace metal;',
           'struct Params {uint seed,count,stride,reserved;};',
           'static uint rol5(uint x){return (x<<5)|(x>>27); }']
    for depth in DEPTHS:
        lines += [f'kernel void depth{depth}(volatile device const uint*input [[buffer(0)]],',
                  'device uint4*output [[buffer(1)]],constant Params&p [[buffer(2)]],uint gid [[thread_position_in_grid]]){',
                  'if(gid>=p.count)return;uint base=gid*p.stride;',
                  'uint state=input[base]+p.seed+gid*747796405u,visits=0;']
        if entry_witness:
            lines[-3]=lines[-3].replace('device uint4*output','volatile device uint4*output')
            lines += [f'output[gid]=uint4(0xface0000u^gid,0x13572468u,{depth}u,0xbabe0000u^gid);']
        for level in range(depth):
            lines += [f'uint limit{level}=1u+((input[base+{level+1}]^p.seed^p.reserved)&1u);',
                      '#pragma clang loop unroll(disable)',
                      f'for(uint iter{level}=0;iter{level}<limit{level};++iter{level}){{',
                      f'state=rol5(state^input[base+{level+1}])+({level}u*2891336453u+iter{level});']
            if level+1<depth:lines += [f'if(iter{level}==0){{']
        for level in reversed(range(depth)):
            if level+1<depth:lines += ['}']
            lines += [f'state=(state*1664525u+1013904223u)^({level}u*97u+iter{level}+p.reserved);',
                      'visits++;','}']
        lines += ['output[gid]=uint4(rol5(state)^p.seed,state,visits,0xcafe0000u^gid);','}']
    return '\n'.join(lines)+'\n'

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--entry-witness',action='store_true');a=p.parse_args()
    out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);(out/'assets').mkdir();(out/'runtime').mkdir()
    (out/'control_flow.metal').write_text(source(a.entry_witness))
    for name in ['control_flow_probe.mm','compiler_output_trace.mm']:shutil.copyfile(ROOT/'tools'/name,out/name)
    for name in ['run_sdk_host.py','lab_gpu_reservation.py']:
        s=ROOT/'sdk-combined/runtime'/name if name=='run_sdk_host.py'else ROOT/'tools'/name
        shutil.copyfile(s,out/'runtime'/name)
    commands=[]
    def run(label,cmd):
        cmd=list(map(str,cmd));start=time.monotonic();r=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
        (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr)
        commands.append({'label':label,'argv':cmd,'exit_code':r.returncode,'monotonic_seconds':time.monotonic()-start});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
        assert r.returncode==0,r.stderr[-2500:];print(label,'PASS',flush=True)
    run('metal',['xcrun','metal','-std=macos-metal2.3','-c',out/'control_flow.metal','-o',out/'control_flow.air'])
    run('metallib',['xcrun','metallib',out/'control_flow.air','-o',out/'assets/control_flow.metallib'])
    for source_,exe,arc in [('control_flow_probe.mm','application','-fobjc-arc'),('compiler_output_trace.mm','compiler_output_trace','-fno-objc-arc')]:
        run(exe,['clang++','-arch','x86_64','-O2','-std=c++17',arc,out/source_,'-framework','Metal','-framework','Foundation','-o',out/exe])
    d={'source_hashes':{n:sha(out/n)for n in ['control_flow.metal','control_flow_probe.mm','compiler_output_trace.mm']},
       'assets_SHA256':{'control_flow.metallib':sha(out/'assets/control_flow.metallib')},
       'runtime_SHA256':{n:sha(out/'runtime'/n)for n in ['run_sdk_host.py','lab_gpu_reservation.py']},
       'executable_SHA256':sha(out/'application'),'capture_executable_SHA256':sha(out/'compiler_output_trace'),
       'source_generator_SHA256':sha(__file__),'depths':DEPTHS,'entry_witness':a.entry_witness,'GPU_execution':False,
       'work_bound':'At most 2*depth loop body visits per thread; the child executes only on iteration0'}
    (out/'inputs.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'status':'PASS','depths':DEPTHS,'GPU_execution':False}))

if __name__=='__main__':main()
