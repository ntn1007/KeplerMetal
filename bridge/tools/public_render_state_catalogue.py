#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Source build and serialized signed GPU reception for owned render states."""
from pathlib import Path
import argparse
import py_compile
import shutil
import sys
import subprocess
import json
import hashlib
from public_large_scratch import ROOT,check_library,check_driver_profile,commands,preflight,read,sha,write
MODES=('gpu','native','pipeline_only','pipeline_only_native','resources_only','resources_only_native','forced_0','forced_1','no_producer','no_consumer','release','contracts')


def build(a):
    out,library=a.out.resolve(),a.library.resolve();preflight(out);m=check_library(library);out.mkdir()
    for name in ['src','assets','runtime','oracles','library-src']:(out/name).mkdir()
    shutil.copyfile(library/'manifest.json',out/'runtime-manifest.json')
    for name in m['source_SHA256']:shutil.copyfile(library/'src'/name,out/'library-src'/name)
    for name in ['KeplerCPUICB.h','KeplerGPUIdentity.h','KeplerRenderCommandRecords.h','KeplerRenderStateRecords.h','KeplerIndirectRenderRangePins.h',
        'render_state_carrier.metal','combined_render_resources.metal','cpu_icb_combined_profiles.json','indirect_render_test.metal','render_state_catalogue.metal','render_state_catalogue_test.metal']:
        shutil.copyfile(ROOT/'src'/name,out/'src'/name)
    for name in ['render_state_catalogue_client.mm','public_render_state_catalogue.py']:shutil.copyfile(ROOT/'tools'/name,out/'src'/name)
    if a.source_commands:
        for name in ['KeplerNativeRenderCommands.h','render_source_commands_test.metal']:
            shutil.copyfile(ROOT/'src'/name,out/'src'/name)
    for name in ['verify_render_state_catalogue.py','verify_indirect_render_ranges.py','verify_local_memory.py','public_large_scratch.py']:
        shutil.copyfile(ROOT/'tools'/name,out/'oracles'/name);py_compile.compile(str(out/'oracles'/name),doraise=True)
    shutil.copyfile(ROOT/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py')
    shutil.copyfile(ROOT/'sdk-combined/runtime/run_sdk_host.py',out/'runtime/run_sdk_host.py')
    run=commands(out)
    for source,name,modules in [('render_state_carrier','render_state_carrier',True),('combined_render_resources','combined_render_resources',True),
        ('indirect_render_test','test',False),('render_state_catalogue','state',False),('render_state_catalogue_test','producer',False)]:
        if name=='producer'and a.source_commands:source='render_source_commands_test'
        flags=[]if modules else['-fmodules=none']
        if name in ['state','producer']:flags+=['-I',out/'src']
        run(name+'-metal',['xcrun','metal','-std=macos-metal2.4',*flags,'-c',out/'src'/(source+'.metal'),'-o',out/(name+'.air')])
        run(name+'-metallib',['xcrun','metallib',out/(name+'.air'),'-o',out/'assets'/(name+'.metallib')])
    for name,digest in [('render_state_carrier','965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7'),('combined_render_resources','3f07a5bb05487244b82001dff6edeed23ace2bd10a32824be1cb727f29f17775')]:
        assert sha(out/'assets'/(name+'.metallib'))==digest
    assert sha(out/'assets/state.metallib')in(out/'src/KeplerIndirectRenderRangePins.h').read_text()
    shutil.copyfile(out/'src/cpu_icb_combined_profiles.json',out/'assets/combined.json')
    run('host',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',out/'src',out/'src/render_state_catalogue_client.mm',library/'libKeplerMetal.a','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',out/'application'])
    write(out/'inputs.json',dict(source_SHA256={str(p.relative_to(out)):sha(p)for p in(out/'src').iterdir()},
        runtime_sources_SHA256=m['source_SHA256'],runtime_SHA256={p.name:sha(p)for p in(out/'runtime').iterdir()},oracle_SHA256={p.name:sha(p)for p in(out/'oracles').iterdir()},
        assets_SHA256={p.name:sha(p)for p in(out/'assets').iterdir()},executable_SHA256=sha(out/'application'),
        static_library_SHA256=m['static_library_SHA256'],library_manifest_SHA256=sha(library/'manifest.json'),source_commands=a.source_commands,GPU_execution=False))


def run(a):
    b,out=a.build.resolve(),a.out.resolve();m=read(b/'inputs.json');assert not out.exists()and out.parent.is_dir()
    for key,folder in [('source_SHA256',''),('runtime_sources_SHA256','library-src'),('runtime_SHA256','runtime'),('oracle_SHA256','oracles'),('assets_SHA256','assets')]:
        for name,digest in m[key].items():assert sha(b/folder/name)==digest,name
    assert sha(b/'runtime-manifest.json')==m['library_manifest_SHA256']and sha(b/'application')==m['executable_SHA256']
    driver=check_driver_profile();out.mkdir();(out/'outputs').mkdir()
    for name in ['src','assets','runtime','oracles','library-src']:shutil.copytree(b/name,out/name)
    shutil.copyfile(b/'runtime-manifest.json',out/'runtime-manifest.json');shutil.copyfile(b/'application',out/'application');(out/'application').chmod(0o755)
    write(out/'inputs.json',dict(m,mode=a.mode,driver_SHA256=driver,source_build_inputs_SHA256=sha(b/'inputs.json')))
    sys.path.insert(0,str(out/'runtime'));from run_sdk_host import run_host
    receipt=run_host(out/'application',out/'execution',list(map(str,[out/'assets',out/'outputs',a.mode])),a.reservation_root.resolve())
    write(out/'results.json',read(out/'execution/execution.stdout'))
    # A fresh isolated interpreter cannot reuse an oracle module imported by
    # this mutable launcher. Every oracle/helper resolves inside the frozen copy.
    code='import sys,json;sys.path.insert(0,sys.argv[1]);from verify_render_state_catalogue import verify;print(json.dumps(verify(sys.argv[2])))'
    argv=[sys.executable,'-I','-c',code,str(out/'oracles'),str(out)]
    verified=subprocess.run(argv,capture_output=True,text=True)
    (out/'verification.stdout').write_text(verified.stdout);(out/'verification.stderr').write_text(verified.stderr)
    write(out/'verification-execution.json',dict(argv=argv,exit_code=verified.returncode,isolated_interpreter=True,code_SHA256=hashlib.sha256(code.encode()).hexdigest()))
    if verified.returncode:raise RuntimeError('Frozen oracle failed; see '+str(out/'verification.stderr'))
    proof=json.loads(verified.stdout);write(out/'independent-verification.json',dict(proof,PID=receipt['pid'],static_library_SHA256=m['static_library_SHA256']))
    print({k:v for k,v in proof.items()if k!='files_SHA256'})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(required=True)
    b=s.add_parser('build');b.add_argument('--library',type=Path,required=True);b.add_argument('--out',type=Path,required=True);b.add_argument('--source-commands',action='store_true');b.set_defaults(func=build)
    r=s.add_parser('run');r.add_argument('--build',type=Path,required=True);r.add_argument('--out',type=Path,required=True);r.add_argument('--mode',choices=MODES,required=True);r.add_argument('--reservation-root',type=Path,required=True);r.set_defaults(func=run)
    a=p.parse_args();a.func(a)
