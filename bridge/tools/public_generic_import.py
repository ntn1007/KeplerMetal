#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fresh full-runtime clients for pinned generic compute/graphics imports.

No downloads, driver changes or old host/library objects. Each run uses the
common signed host reservation. Local compiled fixtures are prerequisites.
"""
from pathlib import Path
import argparse
import json
import os
import shutil
import sys
from public_large_scratch import ROOT, check_library, check_driver_profile, commands, preflight, read, sha, write

CLIENTS = {'vertex':'vertex_io_probe.mm','tess':'tessellation_capture_probe.mm',
           'contract':'generic_import_contract_probe.mm'}


def check_assets(source, pins):
    for name, digest in pins.items():
        assert Path(name).name == name
        assert sha(source / name) == digest, f'Unqualified fixture: {name}'


def build(a):
    out, library = a.out.resolve(), a.library.resolve()
    preflight(out); lm = check_library(library)
    pins = read(ROOT / 'tools/generic_import_fixture_pins.json')
    sources = dict(vertex=a.vertex_assets.resolve(),tess=a.tess_assets.resolve(),cas=a.cas_assets.resolve())
    for group, source in sources.items(): check_assets(source,pins[group])
    out.mkdir()
    for name in ['src','assets','runtime','oracles']: (out / name).mkdir()
    for group, source in sources.items():
        folder = out / 'assets' / group; folder.mkdir()
        for name in pins[group]: shutil.copyfile(source / name,folder / name)
    shutil.copyfile(ROOT / 'tools/generic_import_fixture_pins.json',out / 'assets/pins.json')
    for p in (library / 'src').glob('*.h'): shutil.copyfile(p,out / 'src' / p.name)
    for name in CLIENTS.values(): shutil.copyfile(ROOT / 'tools' / name,out / 'src' / name)
    for name in ['verify_generic_import.py','verify_local_memory.py']:
        shutil.copyfile(ROOT / 'tools' / name,out / 'oracles' / name)
    shutil.copyfile(ROOT / 'tools/lab_gpu_reservation.py',out / 'runtime/lab_gpu_reservation.py')
    shutil.copyfile(ROOT / 'sdk-combined/runtime/run_sdk_host.py',out / 'runtime/run_sdk_host.py')
    command = commands(out)
    for kind, source in CLIENTS.items():
        command(kind,['xcrun','clang++','-arch','x86_64','-O2','-std=c++17',
            '-fobjc-arc' if kind == 'contract' else '-fno-objc-arc',
            '-I',out / 'src',out / 'src' / source,library / 'libKeplerMetal.a',
            '-Wl,-ObjC','-framework','Foundation','-framework','Metal','-o',out / kind])
    frozen = {str(p.relative_to(out)):sha(p) for folder in ['src','assets','runtime','oracles'] for p in (out / folder).rglob('*') if p.is_file()}
    write(out / 'inputs.json',dict(schema=1,static_library_SHA256=lm['static_library_SHA256'],
        library_manifest_SHA256=sha(library / 'manifest.json'),frozen=frozen,
        executables={kind:sha(out / kind) for kind in CLIENTS},builder_SHA256=sha(__file__),
        GPU_execution=False,historical_qualification_inherited=False))


def run(a):
    build, out, reservation = a.build.resolve(), a.out.resolve(), a.reservation_root.resolve()
    assert not out.exists() and out.parent.is_dir() and (reservation / 'results').is_dir()
    inputs = read(build / 'inputs.json')
    for name,digest in inputs['frozen'].items(): assert sha(build / name) == digest,name
    assert sha(build / a.kind) == inputs['executables'][a.kind]
    driver = check_driver_profile()
    if a.kind == 'vertex':
        assert a.mode in ['native','vertex','fragment','both']
        assert a.draw in ['direct','vertex-start','indexed16','indexed32','base-vertex','negative-base-vertex','instanced','base-instance','indirect','indirect-indexed','indirect-control']
    elif a.kind == 'tess': assert a.mode in ['native','imported'] and a.factor in [0,1,2,4,8,16,32,64]
    else: assert a.mode == 'contract'
    out.mkdir(); (out / 'outputs').mkdir()
    for folder in ['src','assets','runtime','oracles']: shutil.copytree(build / folder,out / folder)
    shutil.copyfile(build / a.kind,out / 'application'); (out / 'application').chmod(0o755)
    assets, prefix = out / 'assets', out / 'outputs/capture'
    if a.kind == 'vertex':
        args = [assets / 'vertex/vertex_io_carrier.metallib',assets / 'vertex',a.interpolation,a.draw,a.mode,a.memory]
    elif a.kind == 'tess':
        args = [assets / 'tess/carrier.metallib',a.factor]
        if a.mode == 'imported': args.extend([assets / 'tess/capture.sass',assets / 'tess/capture-info.json'])
    else: args = [assets]
    write(out / 'inputs.json',dict(inputs,kind=a.kind,mode=a.mode,factor=a.factor,
        draw=a.draw,interpolation=a.interpolation,memory=a.memory,driver_SHA256=driver,
        public_runner_SHA256=sha(__file__),source_build_inputs_SHA256=sha(build / 'inputs.json')))
    sys.path.insert(0,str(out / 'runtime'))
    from run_sdk_host import run_host
    environment = {'KEPLER_TESS_CAPTURE_PREFIX':str(prefix),'KEPLER_GRAPHICS_CAPTURE_PREFIX':str(prefix)}
    previous = {k:os.environ.get(k) for k in environment}
    try:
        os.environ.update(environment)
        m = run_host(out / 'application',out / 'execution',list(map(str,args)),reservation)
    finally:
        for key,value in previous.items():
            if value is None: os.environ.pop(key,None)
            else: os.environ[key] = value
    result = read(out / 'execution/execution.stdout'); write(out / 'results.json',result)
    sys.path.insert(0,str(out / 'oracles'))
    from verify_generic_import import verify_vertex, verify_tess, verify_contract
    proof = verify_contract(result) if a.kind == 'contract' else (verify_vertex if a.kind == 'vertex' else verify_tess)(result,prefix)
    def profiles(value):
        if isinstance(value,dict):
            for key,item in value.items():
                if key == 'driver_sha256': assert item == driver
                profiles(item)
        elif isinstance(value,list):
            for item in value: profiles(item)
    profiles(result)
    proof.update(static_library_SHA256=inputs['static_library_SHA256'],
        raw_SHA256={p.name:sha(p) for p in (out / 'outputs').iterdir()},
        device_identity=result['device_identity'],PID=m['pid'])
    write(out / 'independent-verification.json',proof)
    print(json.dumps({k:v for k,v in proof.items() if k not in ['raw_SHA256','device_identity']}),flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__); s = p.add_subparsers(dest='action',required=True)
    q = s.add_parser('build'); q.add_argument('--library',type=Path,required=True)
    for group in ['vertex','tess','cas']: q.add_argument(f'--{group}-assets',type=Path,required=True)
    q.add_argument('--out',type=Path,required=True); q.set_defaults(fn=build)
    q = s.add_parser('run')
    for name in ['build','out','reservation-root']: q.add_argument('--'+name,type=Path,required=True)
    q.add_argument('--kind',choices=list(CLIENTS),required=True); q.add_argument('--mode',required=True)
    q.add_argument('--factor',type=int,default=1);q.add_argument('--draw',default='direct')
    q.add_argument('--interpolation',choices=['smooth','linear','flat'],default='smooth')
    q.add_argument('--memory',choices=['managed','nocopy','private'],default='private');q.set_defaults(fn=run)
    a = p.parse_args(); a.fn(a)


if __name__ == '__main__': main()
