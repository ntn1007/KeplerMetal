#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Add a public CFBundle resolver observer to the qualified native video host."""
from pathlib import Path
import argparse
import hashlib
import json
import plistlib
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


def verify_owned(parent):
    data = load(parent / 'inputs.json')
    if data.get('metadata_capacity') != 512:
        raise ValueError('Qualified capacity512 owned transport required')
    for folder, key in [('', 'source_hashes'), ('assets', 'assets_SHA256'), ('runtime', 'runtime_SHA256')]:
        for name, digest in data[key].items():
            if sha(parent / folder / name) != digest:
                raise ValueError('Qualified owned input changed: ' + name)
    for path, digest in data['reused_objects_and_libraries_SHA256'].items():
        if sha(path) != digest:
            raise ValueError('Qualified prerequisite changed')
    for name, key in [('libVideoOwned.dylib', 'library_SHA256'),
                      ('libVideoRegistryMetadata.dylib', 'metadata_library_SHA256')]:
        if sha(parent / name) != data[key]:
            raise ValueError('Qualified owned library changed')
    from native_video_local_service import verify_parent
    routing = Path(data['parent_build'])
    if sha(routing / 'inputs.json') != data['parent_inputs_SHA256']:
        raise ValueError('Qualified routing manifest changed')
    verify_parent(routing)
    return data


def build(args):
    parent, out = args.owned_build.resolve(), args.out.resolve(); data = verify_owned(parent)
    out.mkdir(exist_ok=False)
    shutil.copytree(parent / 'assets', out / 'assets'); shutil.copytree(parent / 'runtime', out / 'runtime')
    board = plistlib.loads(subprocess.check_output(['ioreg', '-a', '-rd1', '-c', 'IOPlatformExpertDevice']))[0].get('board-id')
    board = board.rstrip(b'\0').decode() if isinstance(board, bytes) else board
    if board != 'Mac-F2268DAE': raise ValueError('Inspected machine board changed')
    write(out / 'assets/factory-policy-profile.json', {'board_id': board, 'source_board': 'Mac-27ADBB7B4CEE8E61'})
    write(out / 'assets/factory-policy-choice.json', {'mode': 'observe'})
    sources = []
    for name in ['video_factory_resolver.mm', 'video_factory_resolver_main.mm', 'video_registry_observer.h']:
        shutil.copyfile(ROOT / 'tools' / name, out / name); sources.append(name)
    shutil.copyfile(parent / 'video_local_service_main.mm', out / 'owned-main.mm'); sources.append('owned-main.mm')
    for source, dest in [(Path(__file__), 'builder.py'),
                         (ROOT / 'tools/native_video_local_service.py', 'runner-base.py'),
                         (ROOT / 'tools/native_video_routing.py', 'parent-verifier.py')]:
        shutil.copyfile(source, out / dest); sources.append(dest)
    for name in ['libVideoOwned.dylib', 'libVideoRegistryMetadata.dylib']:
        shutil.copyfile(parent / name, out / name)
    inherited = dict(data['reused_objects_and_libraries_SHA256'])
    for name in ['libVideoOwned.dylib', 'libVideoRegistryMetadata.dylib']:
        inherited[str(parent / name)] = sha(parent / name)
    entry = next(Path(p) for p in inherited if Path(p).name == 'libVideoRegistry-observer.dylib')
    common = ['clang++', '-arch', 'x86_64', '-O2', '-std=c++17', '-fblocks', '-fno-objc-arc', '-Wno-deprecated-declarations']
    library = out / 'libVideoFactoryResolver.dylib'
    prior = load(parent / 'commands.json')[-1]['argv']
    if prior[-2:] != ['-o', str(parent / 'application')]:
        raise ValueError('Qualified link command changed')
    if prior.count(str(parent / 'main.o')) != 1:
        raise ValueError('Qualified main object not unique')
    linked = []
    for value in prior[:-2]:
        linked.extend([str(out / 'main.o'), str(out / 'owned-main.o')] if value == str(parent / 'main.o') else [value])
    commands = [
        ('resolver-library', common + ['-dynamiclib', out / 'video_factory_resolver.mm', entry,
            '-framework', 'Foundation', '-framework', 'CoreMedia', '-Wl,-undefined,dynamic_lookup',
            '-install_name', library, '-o', library]),
        ('sign-resolver', ['codesign', '--force', '--sign', '-', library]),
        ('owned-main-renamed', common + ['-Dmain=KPOwnedQualifiedMain', '-c', out / 'owned-main.mm', '-o', out / 'owned-main.o']),
        ('resolver-main', common + ['-c', out / 'video_factory_resolver_main.mm', '-o', out / 'main.o']),
        ('application', linked + [str(library), '-o', str(out / 'application')])]
    records = []
    for label, argv in commands:
        argv = list(map(str, argv)); start = time.monotonic()
        p = subprocess.run(argv, capture_output=True, timeout=60)
        (out / (label + '.stdout')).write_bytes(p.stdout); (out / (label + '.stderr')).write_bytes(p.stderr)
        records.append({'label': label, 'argv': argv, 'exit_code': p.returncode,
                        'diagnostic_build_seconds': time.monotonic()-start})
        write(out / 'commands.json', records)
        if p.returncode: raise RuntimeError(label + ': retained stderr')
    write(out / 'assets/factory-resolver-config.json', {'library_SHA256': sha(library)})
    write(out / 'inputs.json', {**data, 'source_hashes': {n: sha(out / n) for n in sources},
        'assets_SHA256': {str(p.relative_to(out / 'assets')): sha(p) for p in (out / 'assets').rglob('*') if p.is_file()},
        'owned_build': str(parent), 'owned_inputs_SHA256': sha(parent / 'inputs.json'),
        'reused_objects_and_libraries_SHA256': inherited,
        'resolver_library_SHA256': sha(library), 'executable_SHA256': sha(out / 'application'),
        'factory_policy_supported': True,
        'new_main_object_SHA256': sha(out / 'main.o'),
        'new_objects_SHA256': {p.name: sha(p) for p in out.glob('*.o')},
        'native_function_invoked_during_build': False, 'GPU_execution': False})
    print(json.dumps({'status': 'BUILT', 'original_owned_transport_libraries_reused': True, 'GPU_work': 0}))


def run(args):
    build = args.build.resolve(); data = load(build / 'inputs.json'); parent = Path(data['owned_build'])
    if sha(parent / 'inputs.json') != data['owned_inputs_SHA256']:
        raise ValueError('Owned parent manifest changed')
    verify_owned(parent)
    if sha(build / 'libVideoFactoryResolver.dylib') != data['resolver_library_SHA256']:
        raise ValueError('Resolver library changed')
    for source, name in [('native_video_local_service.py', 'runner-base.py'), ('native_video_routing.py', 'parent-verifier.py')]:
        if sha(ROOT / 'tools' / source) != data['source_hashes'][name]:
            raise ValueError('Executed Python dependency differs from snapshot')
    from native_video_local_service import run as parent_run
    args.additional_choices = {'factory-policy-choice.json': {'mode': args.policy}}
    parent_run(args)
    shutil.copyfile(args.out / 'outputs/factory-resolver.json', args.out / 'factory-resolver.json')
    shutil.copyfile(__file__, args.out / 'factory-runner.py')
    record = load(args.out / 'factory-resolver.json')
    if record['status'] != 'COMPLETE' or not record['synthetic_controls_valid']:
        raise ValueError('Incomplete resolver observation')
    print(json.dumps({'resolver_status': record['status'], 'native_resolver_calls': record['calls'],
        'controls': record['synthetic_control_calls'], 'returned_pointer_changed': record['resolved_pointer_replaced']}))


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('action', choices=['build', 'run'])
    p.add_argument('--owned-build', type=Path); p.add_argument('--build', type=Path)
    p.add_argument('--out', type=Path, required=True); p.add_argument('--mode', choices=['inspect', 'cpu', 'hardware'])
    p.add_argument('--route', choices=['native', 'owned'], default='native')
    p.add_argument('--override', choices=['native', 'wrong-key', 'present-key'], default='native')
    p.add_argument('--policy', choices=['observe', 'wrong-board', 'current-board'], default='observe')
    p.add_argument('--reservation-root', type=Path, default=ROOT); args = p.parse_args()
    args.out = args.out.resolve(); args.out.relative_to(ROOT / 'results')
    if args.action == 'build':
        if not args.owned_build: p.error('--owned-build required')
        build(args)
    else:
        if not args.build or not args.mode: p.error('--build and --mode required')
        run(args)


if __name__ == '__main__':
    main()
