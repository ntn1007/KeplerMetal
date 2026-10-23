#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build and observe native resource identities, then qualify direct GPU use."""
from pathlib import Path
import argparse
import shutil
import sys
import json
from public_large_scratch import ROOT,check_driver_profile,commands,preflight,read,sha,write

SOURCES = ['tools/native_resource_identity_probe.mm','tools/native_resource_identity_execution.mm',
    'src/native_resource_identity.metal','src/KeplerGPUIdentity.h',
    'tools/native_icb_compile_probe.mm','src/native_icb_compile_probe.metal']


def build(a):
    out = a.out.resolve(); preflight(out); out.mkdir()
    for folder in ['src','runtime','oracles']: (out/folder).mkdir()
    for name in SOURCES: shutil.copyfile(ROOT/name,out/'src'/Path(name).name)
    for name in ['verify_native_resource_identity.py','verify_local_memory.py','public_large_scratch.py']:
        shutil.copyfile(ROOT/'tools'/name,out/'oracles'/name)
    shutil.copyfile(ROOT/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py')
    shutil.copyfile(ROOT/'sdk-combined/runtime/run_sdk_host.py',out/'runtime/run_sdk_host.py')
    command = commands(out)
    command('metal',['xcrun','metal','-std='+a.standard,'-c',out/'src/native_resource_identity.metal','-o',out/'shader.air'])
    command('metallib',['xcrun','metallib',out/'shader.air','-o',out/'shader.metallib'])
    command('icb-metal',['xcrun','metal','-std=macos-metal2.3','-c',out/'src/native_icb_compile_probe.metal','-o',out/'icb.air'])
    command('icb-metallib',['xcrun','metallib',out/'icb.air','-o',out/'icb.metallib'])
    for kind,name in [('inspect','native_resource_identity_probe.mm'),('execute','native_resource_identity_execution.mm'),('icb','native_icb_compile_probe.mm')]:
        command(kind,['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',out/'src',out/'src'/name,
            '-framework','Metal','-framework','Foundation','-o',out/kind])
    frozen = {str(p.relative_to(out)):sha(p) for group in ['src','runtime','oracles'] for p in (out/group).iterdir()}
    frozen['shader.metallib'] = sha(out/'shader.metallib')
    frozen['icb.metallib'] = sha(out/'icb.metallib')
    write(out/'inputs.json',dict(schema=1,standard=a.standard,ICB_probe_standard='macos-metal2.3',frozen=frozen,
        executables={k:sha(out/k) for k in ['inspect','execute','icb']},builder_SHA256=sha(__file__),
        GPU_execution=False,core_runtime_linked=False,interposition=False))


def run(a):
    build,out = a.build.resolve(),a.out.resolve(); assert not out.exists() and out.parent.is_dir()
    inputs = read(build/'inputs.json')
    for name,digest in inputs['frozen'].items(): assert sha(build/name) == digest,name
    kind = 'inspect' if a.mode == 'inspect' else 'icb' if a.mode == 'icb_compile' else 'execute'
    assert sha(build/kind) == inputs['executables'][kind]
    driver = check_driver_profile();out.mkdir();(out/'outputs').mkdir()
    for folder in ['src','runtime','oracles']:shutil.copytree(build/folder,out/folder)
    shutil.copyfile(build/'shader.metallib',out/'shader.metallib')
    if 'icb.metallib' in inputs['frozen']:shutil.copyfile(build/'icb.metallib',out/'icb.metallib')
    shutil.copyfile(build/kind,out/'application');(out/'application').chmod(0o755)
    write(out/'inputs.json',dict(inputs,mode=a.mode,driver_SHA256=driver,executable_SHA256=sha(out/'application'),
        source_build_inputs_SHA256=sha(build/'inputs.json'),public_runner_SHA256=sha(__file__)))
    sys.path.insert(0,str(out/'runtime'));from run_sdk_host import run_host
    argv = [] if kind == 'inspect' else [str(out/'icb.metallib')] if kind == 'icb' else [str(out/'shader.metallib'),a.mode,str(out/'outputs')]
    m = run_host(out/'application',out/'execution',argv,a.reservation_root.resolve())
    result = read(out/'execution/execution.stdout');write(out/'results.json',result)
    sys.path.insert(0,str(out/'oracles'));import verify_native_resource_identity as oracle
    proof = oracle.inspect(result) if kind == 'inspect' else oracle.icb_compile(result) if kind == 'icb' else oracle.execute(result,out/'outputs')
    proof.update(standard=inputs['standard'],PID=m['pid'],driver_SHA256=driver,
        library_SHA256=inputs['frozen']['icb.metallib' if kind == 'icb' else 'shader.metallib'])
    write(out/'independent-verification.json',proof)
    print(json.dumps({k:v for k,v in proof.items()if k!='files_SHA256'}),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='action',required=True)
    q=s.add_parser('build');q.add_argument('--out',type=Path,required=True)
    q.add_argument('--standard',choices=['macos-metal2.3','metal3.0','metal3.2','metal4.0'],default='macos-metal2.3');q.set_defaults(fn=build)
    q=s.add_parser('run')
    for name in ['build','out','reservation-root']:q.add_argument('--'+name,type=Path,required=True)
    q.add_argument('--mode',choices=['inspect','icb_compile','prepare','native','direct','wrong_texture','wrong_sampler','wrong_buffer','no_dispatch'],required=True);q.set_defaults(fn=run)
    a=p.parse_args();a.fn(a)


if __name__=='__main__':main()
