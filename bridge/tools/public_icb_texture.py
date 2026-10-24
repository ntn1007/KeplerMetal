#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Qualify a native texture/sampler argument buffer through existing CPU ICBs.

Build is offline. Every Metal host, including metadata-only, uses the common
reservation and an immutable signed copy. Compiled driver/shader assets are
local outputs only. The caller retains and declares all indirect resources.
"""
from pathlib import Path
import argparse
import shutil
import sys
from public_large_scratch import ROOT, check_library, check_driver_profile, commands, preflight, read, sha, write

MODES = ['metadata'] + [p+s for p in ['native', 'cpu'] for s in ['', '_wrong_texture', '_wrong_sampler', '_wrong_buffer', '_no_dispatch']]


def build(a):
    out, lib = a.out.resolve(), a.library.resolve()
    preflight(out); lm = check_library(lib)
    out.mkdir()
    for folder in ['src', 'runtime', 'oracles']: (out/folder).mkdir()
    for name in ['KeplerGPUIdentity.h', 'KeplerDriverProfile.h', 'KeplerCPUICB.h', 'icb_indirect_texture.metal', 'icb_indirect_texture.json']:
        shutil.copyfile(ROOT/'src'/name, out/'src'/name)
    for name in ['icb_texture_metadata_probe.mm', 'ICBTextureNativeMetadata.inc', 'icb_texture_existing_transport.mm', 'public_icb_texture.py']:
        shutil.copyfile(ROOT/'tools'/name, out/'src'/name)
    for name in ['verify_icb_texture.py', 'verify_local_memory.py', 'public_large_scratch.py']:
        shutil.copyfile(ROOT/'tools'/name, out/'oracles'/name)
    shutil.copyfile(ROOT/'tools/lab_gpu_reservation.py', out/'runtime/lab_gpu_reservation.py')
    shutil.copyfile(ROOT/'sdk-combined/runtime/run_sdk_host.py', out/'runtime/run_sdk_host.py')
    run = commands(out)
    run('metal', ['xcrun','metal','-std=macos-metal2.3','-fmodules=none','-c',out/'src/icb_indirect_texture.metal','-o',out/'consumer.air'])
    run('metallib', ['xcrun','metallib',out/'consumer.air','-o',out/'consumer.metallib'])
    shutil.copyfile(out/'src/icb_indirect_texture.json', out/'consumer-profile.json')
    profile = read(out/'consumer-profile.json')
    assert sha(out/'consumer.metallib') == profile['library_SHA256'], 'Changed native compilation requires a separately qualified profile'
    for kind,source in [('metadata','icb_texture_metadata_probe.mm'), ('transport','icb_texture_existing_transport.mm')]:
        link = [] if kind == 'metadata' else [lib/'libKeplerMetal.a','-Wl,-ObjC']
        run(kind, ['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',out/'src',out/'src'/source,*link,'-framework','Metal','-framework','Foundation','-o',out/kind])
    write(out/'inputs.json', dict(source_SHA256={str(p.relative_to(out)):sha(p) for p in (out/'src').iterdir()},
        runtime_SHA256={p.name:sha(p) for p in (out/'runtime').iterdir()},
        oracle_SHA256={p.name:sha(p) for p in (out/'oracles').iterdir()},
        assets_SHA256={p:sha(out/p) for p in ['consumer.metallib','consumer-profile.json']},
        executables={p:sha(out/p) for p in ['metadata','transport']},
        static_library_SHA256=lm['static_library_SHA256'], library_manifest_SHA256=sha(lib/'manifest.json'),
        builder_SHA256=sha(__file__), GPU_execution=False, SDK_modified=False))


def run(a):
    b, out = a.build.resolve(), a.out.resolve(); m = read(b/'inputs.json')
    assert not out.exists() and out.parent.is_dir()
    for key,folder in [('source_SHA256',''), ('runtime_SHA256','runtime'), ('oracle_SHA256','oracles'), ('assets_SHA256','')]:
        for name,digest in m[key].items(): assert sha(b/folder/name) == digest, name
    kind = 'metadata' if a.mode == 'metadata' else 'transport'
    assert sha(b/kind) == m['executables'][kind]
    driver = check_driver_profile(); out.mkdir(); (out/'outputs').mkdir()
    for folder in ['src','runtime','oracles']: shutil.copytree(b/folder, out/folder)
    for name in m['assets_SHA256']: shutil.copyfile(b/name, out/name)
    shutil.copyfile(b/kind, out/'application'); (out/'application').chmod(0o755)
    write(out/'inputs.json', dict(m, mode=a.mode, driver_SHA256=driver, source_build_inputs_SHA256=sha(b/'inputs.json'), executable_SHA256=sha(out/'application')))
    sys.path.insert(0, str(out/'runtime')); from run_sdk_host import run_host
    arg = m['assets_SHA256']['consumer.metallib'] if kind == 'metadata' else a.mode
    receipt = run_host(out/'application', out/'execution', list(map(str,[out/'consumer.metallib',arg,out/'outputs'])), a.reservation_root.resolve())
    write(out/'results.json', read(out/'execution/execution.stdout'))
    sys.path.insert(0, str(out/'oracles')); import verify_icb_texture
    result = verify_icb_texture.verify(out)
    write(out/'independent-verification.json', dict(result, PID=receipt['pid'], static_library_SHA256=m['static_library_SHA256']))
    print(result)


def main():
    p = argparse.ArgumentParser(description=__doc__); sub = p.add_subparsers(dest='action', required=True)
    b = sub.add_parser('build'); b.add_argument('--library', type=Path, required=True); b.add_argument('--out', type=Path, required=True); b.set_defaults(func=build)
    r = sub.add_parser('run'); r.add_argument('--build', type=Path, required=True); r.add_argument('--out', type=Path, required=True); r.add_argument('--mode', choices=MODES, required=True); r.add_argument('--reservation-root', type=Path, required=True); r.set_defaults(func=run)
    a = p.parse_args(); a.func(a)


if __name__ == '__main__': main()
