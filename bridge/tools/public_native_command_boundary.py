#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Separate native command argument-metadata and intrinsic compiler boundaries."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from public_large_scratch import ROOT,commands,preflight,check_driver_profile,read,sha,write

CASES=('pointer_control','typed_compute_reset','typed_render_reset','raw_compute_reset',
       'raw_render_reset','raw_compute_copy','raw_render_copy','raw_render_draw','raw_render_vertex',
       'witness_control','raw_compute_reset_witness','raw_render_reset_witness',
       'raw_compute_copy_witness','raw_render_copy_witness','raw_render_draw_witness','raw_render_vertex_witness')


def source(case):
    preamble='#include <metal_stdlib>\n#include <metal_command_buffer>\nusing namespace metal;\n'
    witness=case.endswith('_witness')or case=='witness_control'
    if case.endswith('_witness'):case=case[:-8]
    suffix='out[gid]=uint(raw[gid])^0x13579bdu;'if witness else''
    if case=='witness_control':
        return preamble+'kernel void probe_boundary(device ulong *raw [[buffer(0)]],device uint *out [[buffer(1)]],uint gid [[thread_position_in_grid]]) {'+suffix+'}\n'
    if case=='pointer_control':
        return preamble+'kernel void probe_boundary(device ulong *raw [[buffer(0)]],uint gid [[thread_position_in_grid]]) {raw[gid]^=0x13579bdul;}\n'
    typed=case.startswith('typed_');render='_render_'in case;kind='render_command'if render else'compute_command'
    if typed:
        preamble+='struct Arguments { command_buffer commands [[id(0)]]; };\n'
        argument='device Arguments &args';load='command_buffer commands=args.commands;'
    else:
        # Diagnostic representation only. No size/layout equivalence or usable
        # command resource is assumed; the host never supplies or dispatches it.
        argument='device ulong *raw';load='command_buffer commands=*reinterpret_cast<device command_buffer*>(raw);'
    operation='command.reset();'
    if case.endswith('_copy'):operation=kind+' other(commands,gid+1u);command.copy_command(other);'
    if case.endswith('_draw'):operation='command.draw_primitives(primitive_type::triangle,0u,3u,1u,0u);'
    if case.endswith('_vertex'):operation='command.set_vertex_buffer(raw,0u);'
    extra=',device uint *out [[buffer(1)]]'if witness else''
    return preamble+f'kernel void probe_boundary({argument} [[buffer(0)]]{extra},uint gid [[thread_position_in_grid]]) {{\n {load}\n {kind} command(commands,gid);{operation}{suffix}\n}}\n'


def build(a):
    out=a.out.resolve();preflight(out);out.mkdir()
    for name in ['src','runtime','oracles','assets']:(out/name).mkdir()
    for name in ['native_command_boundary_probe.mm','public_native_command_boundary.py','NativeCommandBoundaryCapture.inc']:
        shutil.copyfile(ROOT/'tools'/name,out/'src'/name)
    shutil.copyfile(ROOT/'src/KeplerGPUIdentity.h',out/'src/KeplerGPUIdentity.h')
    for name in ['verify_native_command_boundary.py','verify_local_memory.py','public_large_scratch.py']:
        shutil.copyfile(ROOT/'tools'/name,out/'oracles'/name)
    shutil.copyfile(ROOT/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py')
    shutil.copyfile(ROOT/'sdk-combined/runtime/run_sdk_host.py',out/'runtime/run_sdk_host.py')
    run=commands(out);frontends={}
    for case in CASES:
        path=out/'src'/(case+'.metal');path.write_text('// SPDX-License-Identifier: MIT\n'+source(case))
        argv=list(map(str,['xcrun','metal','-std=macos-metal2.3','-fmodules=none','-c',path,'-o',out/(case+'.air')]))
        p=subprocess.run(argv,capture_output=True,text=True,timeout=60)
        (out/(case+'-metal.stdout')).write_text(p.stdout);(out/(case+'-metal.stderr')).write_text(p.stderr)
        frontends[case]=dict(argv=argv,exit_code=p.returncode)
        if p.returncode:continue
        run(case+'-metallib',['xcrun','metallib',out/(case+'.air'),'-o',out/'assets'/(case+'.metallib')])
        run(case+'-IR',['xcrun','metal','-std=macos-metal2.3','-fmodules=none','-S','-emit-llvm',path,'-o',out/'assets'/(case+'.ll')])
    run('host',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc'if a.capture else'-fobjc-arc','-DKP_COMMAND_CAPTURE='+str(int(a.capture)),'-I',out/'src',out/'src/native_command_boundary_probe.mm','-framework','Metal','-framework','Foundation','-o',out/'application'])
    write(out/'inputs.json',dict(frontends=frontends,
        frozen={str(p.relative_to(out)):sha(p)for folder in ['src','runtime','oracles','assets']for p in(out/folder).iterdir()if p.is_file()},
        executable_SHA256=sha(out/'application'),GPU_execution=False,interposition=a.capture,capture_native_code=a.capture,post_constructor_code=a.capture))


def run(a):
    b,out=a.build.resolve(),a.out.resolve();m=read(b/'inputs.json')
    assert m['frontends'][a.case]['exit_code']==0,'Frontend refused: inspect build; no host launch'
    assert not out.exists()and out.parent.is_dir()
    for name,digest in m['frozen'].items():assert sha(b/name)==digest,name
    assert sha(b/'application')==m['executable_SHA256'];driver=check_driver_profile();out.mkdir()
    for name in ['src','runtime','oracles','assets']:shutil.copytree(b/name,out/name)
    shutil.copyfile(b/'application',out/'application');(out/'application').chmod(0o755)
    write(out/'inputs.json',dict(m,case=a.case,driver_SHA256=driver,source_build_inputs_SHA256=sha(b/'inputs.json')))
    sys.path.insert(0,str(out/'runtime'));from run_sdk_host import run_host
    argv=[str(out/'assets'/(a.case+'.metallib')),a.case]
    if m.get('capture_native_code',False):(out/'captures').mkdir();argv.append(str(out/'captures'))
    receipt=run_host(out/'application',out/'execution',argv,a.reservation_root.resolve())
    write(out/'results.json',read(out/'execution/execution.stdout'))
    code='import sys,json;sys.path.insert(0,sys.argv[1]);from verify_native_command_boundary import verify;print(json.dumps(verify(sys.argv[2])))'
    argv=[sys.executable,'-I','-c',code,str(out/'oracles'),str(out)]
    p=subprocess.run(argv,capture_output=True,text=True)
    (out/'verification.stdout').write_text(p.stdout);(out/'verification.stderr').write_text(p.stderr)
    write(out/'verification-execution.json',dict(argv=argv,exit_code=p.returncode,isolated_interpreter=True,code_SHA256=hashlib.sha256(code.encode()).hexdigest()))
    if p.returncode:raise RuntimeError('Frozen verifier failed; inspect exact terminal host and output')
    proof=json.loads(p.stdout);write(out/'independent-verification.json',dict(proof,PID=receipt['pid']));print(proof)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(required=True)
    b=s.add_parser('build');b.add_argument('--out',type=Path,required=True);b.add_argument('--capture',action='store_true');b.set_defaults(func=build)
    r=s.add_parser('run')
    for name in ['build','out','reservation-root']:r.add_argument('--'+name,type=Path,required=True)
    r.add_argument('--case',choices=CASES,required=True);r.set_defaults(func=run)
    a=p.parse_args();a.func(a)
