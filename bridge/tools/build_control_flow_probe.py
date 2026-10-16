#!/usr/bin/env python3
"""Generate bounded nested loops and freeze a native reference/constructor observer."""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess, time
ROOT=Path(__file__).resolve().parents[1]
DEPTHS=(0,4,8,16,24,40,64,96)
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def source(entry_witness=False,depths=DEPTHS,variant='nested'):
    lines=['// SPDX-License-Identifier: MIT','#include <metal_stdlib>','using namespace metal;',
           'struct Params {uint seed,count,stride,reserved;};',
           'static uint rol5(uint x){return (x<<5)|(x>>27); }']
    for depth in depths:
        lines += [f'kernel void depth{depth}(volatile device const uint*input [[buffer(0)]],',
                  'device uint4*output [[buffer(1)]],constant Params&p [[buffer(2)]],uint gid [[thread_position_in_grid]]){',
                  'if(gid>=p.count)return;uint base=gid*p.stride;',
                  'uint state=input[base]+p.seed+gid*747796405u,visits=0;']
        if entry_witness:
            lines[-3]=lines[-3].replace('device uint4*output','volatile device uint4*output')
            lines += [f'output[gid]=uint4(0xface0000u^gid,0x13572468u,{depth}u,0xbabe0000u^gid);']
        if variant=='pressure':
            words=depth*8
            lines += [f'uint v{i}=input[base+{i%128}];'for i in range(words)]
            lines += ['threadgroup_barrier(mem_flags::mem_device);','uint key=input[base+128]^p.seed;uint checksum=key^gid;']
            lines += [f'checksum=rol5(checksum^v{i})+(key^({i}u*2891336453u));'for i in range(words)]
            lines += [f'output[gid]=uint4(checksum,key,{words}u,0xcafe0000u^gid);','}']
            continue
        for level in range(depth):
            bound=f'1u+((input[base+{level+1}]^p.seed^p.reserved)&1u)'
            if variant!='reload_bounds':lines += [f'uint limit{level}={bound};']
            condition=f'({bound})'if variant=='reload_bounds'else f'limit{level}'
            lines += ['#pragma clang loop unroll(disable)',
                      f'for(uint iter{level}=0;iter{level}<{condition};++iter{level}){{',
                      f'state=rol5(state^input[base+{level+1}])+({level}u*2891336453u+iter{level});']
            if variant=='serial':
                lines += [f'state=(state*1664525u+1013904223u)^({level}u*97u+iter{level}+p.reserved);','visits++;','}']
            elif level+1<depth:lines += [f'if(iter{level}==0){{']
        for level in (reversed(range(depth))if variant!='serial'else []):
            if level+1<depth:lines += ['}']
            lines += [f'state=(state*1664525u+1013904223u)^({level}u*97u+iter{level}+p.reserved);',
                      'visits++;','}']
        lines += ['output[gid]=uint4(rol5(state)^p.seed,state,visits,0xcafe0000u^gid);','}']
    return '\n'.join(lines)+'\n'

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--entry-witness',action='store_true');p.add_argument('--depths',type=int,nargs='+',default=DEPTHS);p.add_argument('--variant',choices=['nested','reload_bounds','serial','pressure'],default='nested');a=p.parse_args()
    if not a.depths or len(a.depths)!=len(set(a.depths))or any(n<0 or n>120 for n in a.depths):p.error('Depths must be distinct, between0 and120 (within the input stride)')
    if a.variant=='pressure'and any(n not in[32,64,96]for n in a.depths):p.error('Pressure case labels32/64/96 denote256/512/768 live values')
    out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);(out/'assets').mkdir();(out/'runtime').mkdir()
    (out/'control_flow.metal').write_text(source(a.entry_witness,a.depths,a.variant))
    (out/'assets/control_flow_config.json').write_text(json.dumps({'variant':a.variant,'depths':a.depths,'entry_witness':a.entry_witness},indent=2)+'\n')
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
       'assets_SHA256':{n:sha(out/'assets'/n)for n in ['control_flow.metallib','control_flow_config.json']},
       'runtime_SHA256':{n:sha(out/'runtime'/n)for n in ['run_sdk_host.py','lab_gpu_reservation.py']},
       'executable_SHA256':sha(out/'application'),'capture_executable_SHA256':sha(out/'compiler_output_trace'),
       'source_generator_SHA256':sha(__file__),'depths':a.depths,'variant':a.variant,'entry_witness':a.entry_witness,'GPU_execution':False,
       'work_bound':('Exactly depth*8 named scalar values folded per thread'if a.variant=='pressure'else
                     'At most 2*depth sequential loop body visits per thread'if a.variant=='serial'else
                     'At most 2*depth nested loop body visits per thread; the child executes only on iteration0')}
    (out/'inputs.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'status':'PASS','depths':a.depths,'variant':a.variant,'GPU_execution':False}))

if __name__=='__main__':main()
