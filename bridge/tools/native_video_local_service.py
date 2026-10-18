#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build/run an opt-in anonymous native video transport, in our process only.

Exact local prerequisite artifacts and a pinned native callback are required.
H.264 software and hardware-required observations stay distinct. No hardware
fallback is hidden; the existing requirement and query gates are preserved.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def verify_parent(parent):
    data = load(parent / 'inputs.json')
    if data.get('routing_schema') != 4:
        raise ValueError('Qualified constructor observer schema4 required')
    for folder, key in [('', 'source_hashes'), ('assets', 'assets_SHA256'), ('runtime', 'runtime_SHA256')]:
        for name, digest in data[key].items():
            if sha(parent / folder / name) != digest:
                raise ValueError('Qualified parent changed: ' + name)
    for name, digest in data['new_object_SHA256'].items():
        if sha(parent / name) != digest:
            raise ValueError('Qualified host object changed: ' + name)
    from native_video_routing import verify_base
    base = Path(data['dependency_build'])
    if sha(base / 'inputs.json') != data['dependency_inputs_SHA256']:
        raise ValueError('Qualified dependency manifest changed')
    _, metadata = verify_base(base)
    return data, base, metadata


def build(args):
    out, parent = args.out.resolve(), args.routing_build.resolve()
    data, base, metadata = verify_parent(parent)
    sdk = Path(subprocess.check_output(['xcrun', '--show-sdk-path'], text=True).strip())
    if sha(sdk / 'usr/include/xpc/xpc.h') != 'cd60da3346b14d4ff08394843b0eca811be7d98aa9cb6b0988004f408c14ba67':
        raise ValueError('Inspected public callback ABI header changed')
    out.mkdir(exist_ok=False)
    shutil.copytree(parent / 'assets', out / 'assets')
    shutil.copytree(parent / 'runtime', out / 'runtime')
    write(out / 'assets/owned-choice.json', {'route': 'native'})
    names = ['video_local_service.mm', 'video_local_service_main.mm',
             'video_registry_metadata.mm', 'video_registry_metadata.h']
    for name in names:
        shutil.copyfile(ROOT / 'tools' / name, out / name)
    shutil.copyfile(__file__, out / 'builder.py')
    shutil.copyfile(ROOT / 'tools/native_video_routing.py', out / 'parent-verifier.py')
    names += ['builder.py', 'parent-verifier.py']
    common = ['clang++', '-arch', 'x86_64', '-O2', '-std=c++17', '-fblocks', '-fno-objc-arc', '-Wno-deprecated-declarations']
    frameworks = ['-framework', 'Foundation', '-framework', 'VideoToolbox', '-framework', 'CoreMedia',
                  '-framework', 'CoreVideo', '-framework', 'Metal', '-framework', 'IOKit']
    library = out / 'libVideoOwned.dylib'
    metadata_library = out / 'libVideoRegistryMetadata.dylib'
    old_metadata = Path(load(base / 'inputs.json')['metadata_build'])
    host = parent / 'qualified-host-renamed.o'
    reused = [host, old_metadata / 'base-catalog.o', old_metadata / 'H264.o',
              base / 'libVideoDependency-both.dylib',
              Path(metadata['qualified_entry_library'])]
    commands = [
        ('metadata-library', common + ['-DKPMETA_CAPACITY=512', '-dynamiclib', out / 'video_registry_metadata.mm',
            *frameworks, '-install_name', metadata_library, '-o', metadata_library]),
        ('sign-metadata', ['codesign', '--force', '--sign', '-', metadata_library]),
        ('owned-library', common + ['-dynamiclib', out / 'video_local_service.mm', *frameworks,
            '-install_name', library, '-o', library]),
        ('sign-owned', ['codesign', '--force', '--sign', '-', library]),
        ('main-object', common + ['-c', out / 'video_local_service_main.mm', '-o', out / 'main.o']),
        ('application', common + [out / 'main.o', *reused, metadata_library, library, *frameworks, '-o', out / 'application'])]
    records = []
    for label, argv in commands:
        argv = list(map(str, argv)); start = time.monotonic()
        p = subprocess.run(argv, capture_output=True, timeout=60)
        (out / (label + '.stdout')).write_bytes(p.stdout)
        (out / (label + '.stderr')).write_bytes(p.stderr)
        records.append({'label': label, 'argv': argv, 'exit_code': p.returncode,
                        'diagnostic_build_seconds': time.monotonic()-start})
        write(out / 'commands.json', records)
        if p.returncode:
            raise RuntimeError(label + ': retained stderr')
    registry = load(out / 'assets/registry-config.json')
    registry['metadata_library_SHA256'] = sha(metadata_library)
    write(out / 'assets/registry-config.json', registry)
    write(out / 'inputs.json', {'schema': 1,
        'source_hashes': {n: sha(out / n) for n in names},
        'runtime_SHA256': data['runtime_SHA256'],
        'assets_SHA256': {str(p.relative_to(out / 'assets')): sha(p) for p in (out / 'assets').rglob('*') if p.is_file()},
        'parent_build': str(parent), 'parent_inputs_SHA256': sha(parent / 'inputs.json'),
        'dependency_build': str(base), 'reused_objects_and_libraries_SHA256': {str(p): sha(p) for p in reused},
        'library_SHA256': sha(library), 'metadata_library_SHA256': sha(metadata_library),
        'metadata_capacity': 512, 'executable_SHA256': sha(out / 'application'),
        'new_main_object_SHA256': sha(out / 'main.o'), 'GPU_execution': False,
        'native_callback_invoked_during_build': False, 'system_modified': False})
    print(json.dumps({'status': 'BUILT', 'GPU_work': 0, 'native_callback_invoked': False}))


def run(args):
    build, out = args.build.resolve(), args.out.resolve()
    data = load(build / 'inputs.json')
    if args.override != 'native' and args.mode != 'hardware':
        raise ValueError('Presence counterfactual restricted to hardware-required calls')
    for folder, key in [('', 'source_hashes'), ('assets', 'assets_SHA256'), ('runtime', 'runtime_SHA256')]:
        for name, digest in data[key].items():
            if sha(build / folder / name) != digest:
                raise ValueError('Frozen input changed: ' + name)
    for path, digest in data['reused_objects_and_libraries_SHA256'].items():
        if sha(path) != digest:
            raise ValueError('Reused artifact changed')
    parent = Path(data['parent_build'])
    if sha(parent / 'inputs.json') != data['parent_inputs_SHA256']:
        raise ValueError('Parent manifest changed')
    verify_parent(parent)
    if sha(build / 'application') != data['executable_SHA256'] or sha(build / 'libVideoOwned.dylib') != data['library_SHA256']:
        raise ValueError('Executable/library changed')
    if 'metadata_library_SHA256' in data and sha(build / 'libVideoRegistryMetadata.dylib') != data['metadata_library_SHA256']:
        raise ValueError('Own metadata library changed')
    out.mkdir(exist_ok=False); (out / 'outputs').mkdir()
    shutil.copytree(build / 'assets', out / 'assets')
    write(out / 'assets/owned-choice.json', {'route': args.route})
    write(out / 'assets/dependency-choice.json', {'mode': args.override})
    for name in data['source_hashes']:
        shutil.copyfile(build / name, out / name)
    shutil.copyfile(__file__, out / 'runner.py')
    shutil.copyfile(build / 'application', out / 'application'); (out / 'application').chmod(0o755)
    assets = {**data['assets_SHA256'], **{n: sha(out / 'assets' / n) for n in ['owned-choice.json', 'dependency-choice.json']}}
    write(out / 'inputs.json', {**data, 'assets_SHA256': assets, 'mode': args.mode, 'route': args.route,
                              'override_mode': args.override})
    sys.path.insert(0, str(build / 'runtime'))
    from run_sdk_host import run_host
    manifest = run_host(out / 'application', out / 'execution',
        [str(out / 'assets'), str(out / 'outputs'), args.mode], args.reservation_root.resolve())
    result = load(out / 'execution/execution.stdout'); write(out / 'results.json', result)
    for name in ['owned.json', 'images.json'] + ([] if args.mode == 'inspect' else ['dependency.json', 'metadata.json']):
        shutil.copyfile(out / 'outputs' / name, out / name)
    own = load(out / 'owned.json'); decoded = result.get('public_decode')
    print(json.dumps({'status': 'PROCESS_COMPLETED', 'PID': manifest['pid'], 'route': args.route,
        'mode': args.mode, 'native_callback_returned': own['native_callback_returned'],
        'owned_constructors': own['constructor_calls'],
        'create_status': decoded['decode']['create_status'] if decoded else None,
        'output_frames': decoded['output_frames'] if decoded else 0,
        'different_bytes': decoded['different_bytes'] if decoded else None,
        'hardware_video_execution_proved': False}))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['build', 'run'])
    p.add_argument('--routing-build', type=Path); p.add_argument('--build', type=Path)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--mode', choices=['inspect', 'cpu', 'hardware'])
    p.add_argument('--route', choices=['native', 'owned'], default='native')
    p.add_argument('--override', choices=['native', 'wrong-key', 'present-key'], default='native')
    p.add_argument('--reservation-root', type=Path, default=ROOT)
    args = p.parse_args(); args.out.resolve().relative_to(ROOT / 'results')
    if args.action == 'build':
        if not args.routing_build: p.error('--routing-build required')
        build(args)
    else:
        if not args.build or not args.mode: p.error('--build and --mode required')
        run(args)


if __name__ == '__main__':
    main()
