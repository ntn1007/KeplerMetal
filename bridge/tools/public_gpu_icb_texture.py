#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Native source-generated compute commands consuming native texture arguments."""
from pathlib import Path
import argparse
import shutil
import sys
from public_large_scratch import ROOT,check_library,check_driver_profile,commands,preflight,read,sha,write
from public_native_msl_commands import msl_abi

MODES=['gpu','gpu_wrong_texture','gpu_wrong_sampler','gpu_wrong_buffer','gpu_no_producer','gpu_no_consumer']
ASSETS=['gpu_command_selector.metallib','gpu_command_geometry.metallib','gpu_command_bindings.metallib','materializer.metallib']


def build(a):
    out,lib,assets=a.out.resolve(),a.library.resolve(),a.command_assets.resolve()
    preflight(out);lm=check_library(lib);pins=read(ROOT/'tools/native_msl_fixture_pins.json')['assets']
    for name in ASSETS:assert sha(assets/name)==pins[name],name
    out.mkdir()
    for folder in ['src','include','runtime','oracles']:(out/folder).mkdir()
    for name in ['KeplerGPUIdentity.h','KeplerDriverProfile.h','KeplerCPUICB.h','KeplerCommandIR.h','KeplerNativeMSLCommands.h','icb_indirect_texture.metal','icb_indirect_texture.json','gpu_icb_texture_producer.metal']:
        shutil.copyfile(ROOT/'src'/name,out/'src'/name)
    for name in ['icb_texture_gpu_commands.mm','public_gpu_icb_texture.py','public_native_msl_commands.py','native_msl_fixture_pins.json']:
        shutil.copyfile(ROOT/'tools'/name,out/'src'/name)
    for name in ['verify_gpu_icb_texture.py','verify_gpu_icb_texture_rows.py','verify_local_memory.py','public_large_scratch.py']:
        shutil.copyfile(ROOT/'tools'/name,out/'oracles'/name)
    shutil.copyfile(ROOT/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py')
    shutil.copyfile(ROOT/'sdk-combined/runtime/run_sdk_host.py',out/'runtime/run_sdk_host.py')
    for name in ASSETS:shutil.copyfile(assets/name,out/name)
    (out/'include/KeplerCommandIR.h').write_text(msl_abi((out/'src/KeplerCommandIR.h').read_text()))
    shutil.copyfile(out/'src/KeplerNativeMSLCommands.h',out/'include/metal_command_buffer')
    run=commands(out)
    for name,source,flags in [('consumer','icb_indirect_texture',[]),('producer','gpu_icb_texture_producer',['-I',out/'include'])]:
        run(name+'-metal',['xcrun','metal','-std=macos-metal2.3','-fmodules=none',*flags,'-c',out/'src'/(source+'.metal'),'-o',out/(name+'.air')])
        run(name+'-metallib',['xcrun','metallib',out/(name+'.air'),'-o',out/(name+'.metallib')])
    shutil.copyfile(out/'src/icb_indirect_texture.json',out/'consumer-profile.json')
    assert sha(out/'consumer.metallib')==read(out/'consumer-profile.json')['library_SHA256']
    run('host',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',out/'src',out/'src/icb_texture_gpu_commands.mm',lib/'libKeplerMetal.a','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',out/'application'])
    write(out/'inputs.json',dict(source_SHA256={str(p.relative_to(out)):sha(p)for folder in ['src','include']for p in(out/folder).iterdir()},
        runtime_SHA256={p.name:sha(p)for p in(out/'runtime').iterdir()},oracle_SHA256={p.name:sha(p)for p in(out/'oracles').iterdir()},
        assets_SHA256={name:sha(out/name)for name in ASSETS+['consumer.metallib','consumer-profile.json','producer.metallib']},
        executable_SHA256=sha(out/'application'),static_library_SHA256=lm['static_library_SHA256'],library_manifest_SHA256=sha(lib/'manifest.json'),
        builder_SHA256=sha(__file__),SDK_modified=False,GPU_execution=False))


def run(a):
    b,out=a.build.resolve(),a.out.resolve();m=read(b/'inputs.json');assert not out.exists()and out.parent.is_dir()
    for key,folder in [('source_SHA256',''),('runtime_SHA256','runtime'),('oracle_SHA256','oracles'),('assets_SHA256','')]:
        for name,digest in m[key].items():assert sha(b/folder/name)==digest,name
    assert sha(b/'application')==m['executable_SHA256'];driver=check_driver_profile()
    out.mkdir();(out/'outputs').mkdir()
    for folder in ['src','include','runtime','oracles']:shutil.copytree(b/folder,out/folder)
    for name in m['assets_SHA256']:shutil.copyfile(b/name,out/name)
    shutil.copyfile(b/'application',out/'application');(out/'application').chmod(0o755)
    write(out/'inputs.json',dict(m,mode=a.mode,driver_SHA256=driver,source_build_inputs_SHA256=sha(b/'inputs.json')))
    sys.path.insert(0,str(out/'runtime'));from run_sdk_host import run_host
    receipt=run_host(out/'application',out/'execution',list(map(str,[out/'consumer.metallib',a.mode,out/'outputs'])),a.reservation_root.resolve())
    write(out/'results.json',read(out/'execution/execution.stdout'))
    sys.path.insert(0,str(out/'oracles'));import verify_gpu_icb_texture
    proof=verify_gpu_icb_texture.verify(out)
    write(out/'independent-verification.json',dict(proof,PID=receipt['pid'],static_library_SHA256=m['static_library_SHA256']))
    print({k:v for k,v in proof.items()if k not in ['files_SHA256','device_identity']})


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(required=True)
    b=s.add_parser('build');b.add_argument('--library',type=Path,required=True);b.add_argument('--command-assets',type=Path,required=True);b.add_argument('--out',type=Path,required=True);b.set_defaults(func=build)
    r=s.add_parser('run');r.add_argument('--build',type=Path,required=True);r.add_argument('--out',type=Path,required=True);r.add_argument('--mode',choices=MODES,required=True);r.add_argument('--reservation-root',type=Path,required=True);r.set_defaults(func=run)
    a=p.parse_args();a.func(a)
