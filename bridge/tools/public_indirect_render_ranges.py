#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build and run the bounded GPU-controlled render ICB execution-range client."""
from pathlib import Path
import argparse
import shutil
import py_compile
import sys
from public_large_scratch import ROOT,commands,check_library,check_driver_profile,preflight,read,sha,write


def build(a):
    out,lib=a.out.resolve(),a.library.resolve();preflight(out);m=check_library(lib);out.mkdir()
    for folder in ['src','assets','runtime','oracles','library-src']:(out/folder).mkdir()
    shutil.copyfile(lib/'manifest.json',out/'runtime-manifest.json')
    for name in m['source_SHA256']:shutil.copyfile(lib/'src'/name,out/'library-src'/name)
    for name in ['KeplerCPUICB.h','KeplerGPUIdentity.h','render_state_carrier.metal','vertex_io_carrier.metal','combined_render_resources.metal','cpu_icb_combined_profiles.json','indirect_render_range.metal','indirect_render_test.metal','render_command_records.metal','KeplerRenderCommandRecords.h','cpu_icb_indexed_profiles.json','KeplerIndirectRenderRangePins.h']:shutil.copyfile(ROOT/'src'/name,out/'src'/name)
    for name in ['indirect_render_range_client.mm','public_indirect_render_ranges.py']:shutil.copyfile(ROOT/'tools'/name,out/'src'/name)
    for name in ['verify_indirect_render_ranges.py','verify_local_memory.py','public_large_scratch.py']:shutil.copyfile(ROOT/'tools'/name,out/'oracles'/name)
    shutil.copyfile(ROOT/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py');shutil.copyfile(ROOT/'sdk-combined/runtime/run_sdk_host.py',out/'runtime/run_sdk_host.py')
    for p in(out/'oracles').glob('*.py'):py_compile.compile(str(p),doraise=True)
    run=commands(out)
    for source,name in [('render_state_carrier','render_state_carrier'),('vertex_io_carrier','vertex_io_carrier'),('combined_render_resources','combined_render_resources'),('indirect_render_range','range'),('render_command_records','records'),('indirect_render_test','test')]:
        flags=['-fmodules=none']if name in ['range','records','test']else[]
        if name=='records':flags+=['-I',out/'src']
        run(name+'-metal',['xcrun','metal','-std=macos-metal2.4',*flags,'-c',out/'src'/(source+'.metal'),'-o',out/(name+'.air')]);run(name+'-metallib',['xcrun','metallib',out/(name+'.air'),'-o',out/'assets'/(name+'.metallib')])
    for name,digest in [('render_state_carrier','965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7'),('vertex_io_carrier','c0e24e5a5534e10f0eca591b5ace2112d76eafde74ed297ce1b3df0d95b5ca43'),('combined_render_resources','3f07a5bb05487244b82001dff6edeed23ace2bd10a32824be1cb727f29f17775')]:assert sha(out/'assets'/(name+'.metallib'))==digest
    assert sha(out/'assets/records.metallib')in(out/'src/KeplerIndirectRenderRangePins.h').read_text()
    assert sha(out/'assets/range.metallib')in(out/'src/KeplerIndirectRenderRangePins.h').read_text()
    shutil.copyfile(out/'src/cpu_icb_indexed_profiles.json',out/'assets/vertex.json')
    shutil.copyfile(out/'src/cpu_icb_combined_profiles.json',out/'assets/combined.json')
    run('host',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',out/'src',out/'src/indirect_render_range_client.mm',lib/'libKeplerMetal.a','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',out/'application'])
    write(out/'inputs.json',dict(runtime_sources_SHA256=m['source_SHA256'],source_SHA256={str(p.relative_to(out)):sha(p)for p in(out/'src').iterdir()},runtime_SHA256={p.name:sha(p)for p in(out/'runtime').iterdir()},oracle_SHA256={p.name:sha(p)for p in(out/'oracles').iterdir()},assets_SHA256={p.name:sha(p)for p in(out/'assets').iterdir()},executable_SHA256=sha(out/'application'),static_library_SHA256=m['static_library_SHA256'],library_manifest_SHA256=sha(lib/'manifest.json'),GPU_execution=False))


def run(a):
    b,out=a.build.resolve(),a.out.resolve();m=read(b/'inputs.json');assert not out.exists()and out.parent.is_dir()
    assert set(m['runtime_SHA256'])=={'run_sdk_host.py','lab_gpu_reservation.py'}
    for key,folder in [('source_SHA256',''),('runtime_SHA256','runtime'),('oracle_SHA256','oracles'),('assets_SHA256','assets'),('runtime_sources_SHA256','library-src')]:
        for name,digest in m[key].items():assert sha(b/folder/name)==digest,name
    assert sha(b/'application')==m['executable_SHA256'];driver=check_driver_profile();out.mkdir();(out/'outputs').mkdir()
    assert sha(b/'runtime-manifest.json')==m['library_manifest_SHA256']
    shutil.copyfile(b/'runtime-manifest.json',out/'runtime-manifest.json')
    for folder in ['src','assets','runtime','oracles','library-src']:shutil.copytree(b/folder,out/folder)
    shutil.copyfile(b/'application',out/'application');(out/'application').chmod(0o755);write(out/'inputs.json',dict(m,mode=a.mode,driver_SHA256=driver,source_build_inputs_SHA256=sha(b/'inputs.json')))
    sys.path.insert(0,str(out/'runtime'));from run_sdk_host import run_host
    receipt=run_host(out/'application',out/'execution',list(map(str,[out/'assets',out/'outputs',a.mode])),a.reservation_root.resolve())
    write(out/'results.json',read(out/'execution/execution.stdout'));sys.path.insert(0,str(out/'oracles'));import verify_indirect_render_ranges
    proof=verify_indirect_render_ranges.verify(out);write(out/'independent-verification.json',dict(proof,PID=receipt['pid'],static_library_SHA256=m['static_library_SHA256']));print({k:v for k,v in proof.items()if k!='files_SHA256'})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(required=True)
    b=s.add_parser('build');b.add_argument('--library',type=Path,required=True);b.add_argument('--out',type=Path,required=True);b.set_defaults(func=build)
    r=s.add_parser('run');r.add_argument('--build',type=Path,required=True);r.add_argument('--out',type=Path,required=True);r.add_argument('--mode',choices=['gpu','native','no_consumer','lifetime','contracts','fragment','fragment_native','fragment_lifetime','legacy','legacy_native','release','fragment_release','records','records_native','fragment_records','fragment_records_native','records_no_consumer','records_no_producer','records_release','fragment_records_release'],required=True);r.add_argument('--reservation-root',type=Path,required=True);r.set_defaults(func=run)
    a=p.parse_args();a.func(a)
