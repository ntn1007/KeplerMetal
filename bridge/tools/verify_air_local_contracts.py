#!/usr/bin/env python3
"""Compile valid MSL with unsupported resource contracts and verify CPU rejection."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler-build',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();build=a.compiler_build.resolve();out=a.out.resolve()
    out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
    manifest=json.loads((build/'manifest.json').read_text())
    assert sha(build/'compiler')==manifest['compiler_SHA256']
    for f,h in manifest['source_SHA256'].items():assert sha(build/f)==h
    text='''#include <metal_stdlib>
using namespace metal;
struct LocalParams {uint seed,count,stride,reserved;};
kernel void local_control(volatile device const uint *input [[buffer(0)]],
 device uint4 *output [[buffer(1)]], constant LocalParams &p [[buffer(2)]],
 uint gid [[thread_position_in_grid]]) {
 output[gid]=uint4(input[gid]^p.seed,p.count,p.stride,gid);
}
'''
    variants={
        'device_constant_pointer':text.replace('constant LocalParams &p','device LocalParams &p'),
        'larger_constant_struct':text.replace('stride,reserved;','stride,reserved,extra;'),
        'swapped_bindings':text.replace('buffer(0)','buffer(TEMP)').replace('buffer(1)','buffer(0)').replace('buffer(TEMP)','buffer(1)'),
        'different_constant_binding':text.replace('buffer(2)','buffer(3)'),
        'dynamic_constant_offset':text.replace('p.seed','((constant uint *)&p)[gid&3u]'),
    }
    commands=[];records=[]
    def run(label,argv,expected=0):
        argv=list(map(str,argv));env=os.environ.copy();env.pop('NAK_DEBUG',None)
        start=time.monotonic();r=subprocess.run(argv,capture_output=True,text=True,env=env,timeout=60)
        (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr)
        commands.append({'label':label,'argv':argv,'exit_code':r.returncode,
                         'expected_exit_code':expected,'monotonic_seconds':time.monotonic()-start})
        (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
        assert r.returncode==expected,(label,r.returncode,r.stderr[-2000:])
        print(label,'PASS',flush=True);return r
    for name,source in variants.items():
        case=out/name;case.mkdir();(case/'test.metal').write_text(source)
        run(name+'-metal',['xcrun','metal','-std=macos-metal2.3','-c',case/'test.metal','-o',case/'test.air'])
        expected=20 if name=='dynamic_constant_offset' else 11
        r=run(name+'-reject',[build/'compiler',case/'test.air',case,'local_control',32,2],expected)
        assert not (case/'program.sass').exists()
        if expected==11:assert 'Unsupported local AIR entry types/address spaces' in r.stderr
        else:assert 'Unsupported local AIR field' in r.stderr
        records.append({'name':name,'status':'PASS','expected_rejection':expected,
                        'MSL_SHA256':sha(case/'test.metal'),'AIR_SHA256':sha(case/'test.air')})
    for name,entry,bank,expected in [('missing_entry','absent',2,9),('wrong_constant_bank','local_control',0,2),
                                     ('valid_after_rejections','local_control',2,0)]:
        case=out/name;case.mkdir()
        run(name,[build/'compiler',build/'local_memory.air',case,entry,32,bank],expected)
        if not expected:assert sha(case/'program.sass')==sha(build/'local_control.sass')
        else:assert not (case/'program.sass').exists()
        records.append({'name':name,'status':'PASS','expected_rejection':expected})
    assert sha(build/'compiler')==manifest['compiler_SHA256']
    result={'status':'PASS','cases':records,'compiler_SHA256':manifest['compiler_SHA256'],
            'compiler_manifest_SHA256':sha(build/'manifest.json'),'verifier_SHA256':sha(__file__),
            'GPU_execution':False,'full_objective_complete':False}
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':'PASS','cases':len(records),'GPU_execution':False}))

if __name__=='__main__':main()
