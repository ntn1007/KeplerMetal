#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build a public-XPC observer around the qualified codec host source.

The original main's source is unchanged and compiled with a different entry
name. Its object is therefore new; decoder/catalog objects and transport
libraries are reused exactly. No GPU work occurs during compilation.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def verify_base(base):
    data = load(base / 'inputs.json')
    for folder, key in [('', 'source_hashes'), ('assets', 'assets_SHA256'), ('runtime', 'runtime_SHA256')]:
        for name, digest in data[key].items():
            if sha(base / folder / name) != digest:
                raise ValueError('Qualified dependency input changed: ' + name)
    for kind, digest in data['dependency_libraries_SHA256'].items():
        if sha(base / ('libVideoDependency-' + kind + '.dylib')) != digest:
            raise ValueError('Qualified dependency library changed')
    parent = Path(data['metadata_build'])
    if sha(parent / 'inputs.json') != data['metadata_inputs_SHA256']:
        raise ValueError('Qualified metadata manifest changed')
    pi = load(parent / 'inputs.json')
    for name, digest in pi['object_SHA256'].items():
        if sha(parent / name) != digest:
            raise ValueError('Qualified object changed')
    if sha(parent / 'libVideoRegistryMetadata.dylib') != data['qualified_metadata_library_SHA256'] \
            or sha(pi['qualified_entry_library']) != data['qualified_entry_library_SHA256']:
        raise ValueError('Qualified entry/metadata library changed')
    return data, pi


def build(args):
    base, out = args.dependency_build.resolve(), args.out.resolve()
    data, pi = verify_base(base)
    parent = Path(data['metadata_build'])
    profile = load(args.profile)
    if len(profile['modules']) != 7 or len(profile['required_before_begin']) != 3:
        raise ValueError('Inspected public-API module profile required')
    if len(re.findall(r'\bmain\b', (base / 'video_registry_client.mm').read_text())) != 1:
        raise ValueError('Qualified source entry no longer unique')
    out.mkdir(exist_ok=False)
    shutil.copytree(base / 'assets', out / 'assets')
    shutil.copytree(base / 'runtime', out / 'runtime')
    shutil.copyfile(args.profile, out / 'assets/routing-profile.json')
    write(out / 'assets/routing-choice.json', {'mode': 'observe'})
    write(out / 'assets/peer-choice.json', {'mode': 'observe'})
    shutil.copyfile(base / 'inputs.json', out / 'dependency-inputs.json')
    names = []
    for name in data['source_hashes']:
        target = 'dependency-builder.py' if name == 'builder.py' else name
        shutil.copyfile(base / name, out / target)
        names.append(target)
    for name in ['video_routing.h', 'video_routing.mm', 'video_routing_main.mm']:
        shutil.copyfile(ROOT / 'tools' / name, out / name)
        names.append(name)
    shutil.copyfile(Path(__file__), out / 'builder.py')
    names.append('builder.py')
    common = ['clang++', '-arch', 'x86_64', '-O2', '-std=c++17', '-fno-objc-arc', '-fblocks', '-Wno-deprecated-declarations']
    frameworks = ['-framework', 'Foundation', '-framework', 'CoreMedia', '-framework', 'VideoToolbox',
                  '-framework', 'CoreVideo', '-framework', 'Metal', '-framework', 'IOKit']
    library = out / 'libVideoRouting.dylib'
    host, wrapper = out / 'qualified-host-renamed.o', out / 'routing-main.o'
    commands = [
        ('routing-library', common + ['-dynamiclib', out / 'video_routing.mm', *frameworks,
            '-install_name', library, '-o', library]),
        ('sign-routing', ['codesign', '--force', '--sign', '-', library]),
        ('qualified-host-renamed', common + ['-DKPREG_CALIBRATION=0', '-Dmain=KPRegistryQualifiedMain',
            '-c', out / 'video_registry_client.mm', '-o', host]),
        ('routing-main', common + ['-c', out / 'video_routing_main.mm', '-o', wrapper])]
    for codec, kind in [('H264', 'both'), ('MPEG2Video', 'observer')]:
        commands.append((codec, common + [host, wrapper, parent / 'base-catalog.o', parent / (codec + '.o'),
            library, base / ('libVideoDependency-' + kind + '.dylib'), parent / 'libVideoRegistryMetadata.dylib',
            pi['qualified_entry_library'], *frameworks, '-o', out / ('application-' + codec)]))
    records = []
    for label, argv in commands:
        argv = list(map(str, argv))
        started = time.monotonic()
        q = subprocess.run(argv, capture_output=True, timeout=60)
        (out / (label + '.stdout')).write_bytes(q.stdout)
        (out / (label + '.stderr')).write_bytes(q.stderr)
        records.append({'label': label, 'argv': argv, 'exit_code': q.returncode,
                        'diagnostic_build_seconds': time.monotonic() - started})
        write(out / 'commands.json', records)
        if q.returncode:
            raise RuntimeError(label + ': inspect retained stderr')
    write(out / 'assets/routing-config.json', {'library_SHA256': sha(library),
          'profile_SHA256': sha(out / 'assets/routing-profile.json')})
    write(out / 'inputs.json', {
        'routing_schema': 4, 'source_hashes': {n: sha(out / n) for n in names},
        'assets_SHA256': {str(p.relative_to(out / 'assets')): sha(p) for p in (out / 'assets').rglob('*') if p.is_file()},
        'runtime_SHA256': {p.name: sha(p) for p in (out / 'runtime').iterdir()},
        'dependency_build': str(base), 'dependency_inputs_SHA256': sha(base / 'inputs.json'),
        'qualified_host_source_SHA256': sha(base / 'video_registry_client.mm'),
        'qualified_host_object_reused': False, 'qualified_host_source_unchanged': True,
        'catalog_and_decoder_objects_reused': True, 'routing_library_SHA256': sha(library),
        'new_object_SHA256': {p.name: sha(p) for p in out.glob('*.o')},
        'executable_variants_SHA256': {c: sha(out / ('application-' + c)) for c in ['H264', 'MPEG2Video']},
        'GPU_execution': False, 'unknown_private_function_invoked_by_host': False})
    print(json.dumps({'status': 'BUILT', 'variants': 2, 'new_renamed_host_object': True,
                      'qualified_host_source_unchanged': True, 'GPU_work': 0}))


def run(args):
    build_root, out = args.build.resolve(), args.out.resolve()
    data = load(build_root / 'inputs.json')
    for folder, key in [('', 'source_hashes'), ('assets', 'assets_SHA256'), ('runtime', 'runtime_SHA256')]:
        for name, digest in data[key].items():
            if sha(build_root / folder / name) != digest:
                raise ValueError('Frozen routing input changed: ' + name)
    base = Path(data['dependency_build'])
    if sha(base / 'inputs.json') != data['dependency_inputs_SHA256']:
        raise ValueError('Qualified dependency manifest changed')
    verify_base(base)
    if sha(build_root / 'libVideoRouting.dylib') != data['routing_library_SHA256']:
        raise ValueError('Routing library changed')
    if args.override != 'native' and (args.codec != 'H264' or args.mode != 'hardware'):
        raise ValueError('Counterfactual restricted to H264 hardware')
    has_peer = data.get('routing_schema') in (3, 4)
    if args.peer is not None and not has_peer:
        raise ValueError('Peer metadata mode requires observer schema 3')
    binary = build_root / ('application-' + args.codec)
    expected = data['executable_variants_SHA256'][args.codec]
    if sha(binary) != expected:
        raise ValueError('Executable changed')
    out.mkdir(exist_ok=False)
    (out / 'outputs').mkdir()
    shutil.copytree(build_root / 'assets', out / 'assets')
    write(out / 'assets/dependency-choice.json', {'mode': args.override})
    write(out / 'assets/routing-choice.json', {'mode': args.routing})
    if has_peer:
        write(out / 'assets/peer-choice.json', {'mode': args.peer or 'observe'})
    for name in data['source_hashes']:
        shutil.copyfile(build_root / name, out / name)
    shutil.copyfile(Path(__file__), out / 'runner.py')
    shutil.copyfile(binary, out / 'application')
    (out / 'application').chmod(0o755)
    assets = dict(data['assets_SHA256'])
    for name in ['dependency-choice.json', 'routing-choice.json'] + (['peer-choice.json'] if has_peer else []):
        assets[name] = sha(out / 'assets' / name)
    write(out / 'inputs.json', {**data, 'assets_SHA256': assets, 'selected_codec': args.codec,
        'override_mode': args.override, 'routing_mode': args.routing, 'peer_mode': (args.peer or 'observe') if has_peer else None,
        'executable_SHA256': expected})
    sys.path.insert(0, str(build_root / 'runtime'))
    from run_sdk_host import run_host
    manifest = run_host(out / 'application', out / 'execution',
        [str(out / 'assets'), str(out / 'outputs'), args.mode], args.reservation_root.resolve())
    result = json.loads((out / 'execution/execution.stdout').read_text())
    write(out / 'results.json', result)
    files = ['images.json', 'routing.json'] + ([] if args.mode == 'inspect' else ['dependency.json', 'metadata.json'])
    for filename in files:
        shutil.copyfile(out / 'outputs' / filename, out / filename)
    routing = load(out / 'routing.json')
    if routing['status'] != 'COMPLETE' or not routing['synthetic_controls_valid']:
        raise ValueError('Incomplete routing observation')
    verify_base(base)
    decoded = result.get('public_decode')
    native = [e for e in routing['events'] if not e['synthetic_control']]
    print(json.dumps({'status': 'PROCESS_COMPLETED', 'codec': args.codec, 'mode': args.mode,
        'override': args.override, 'routing': args.routing, 'PID': manifest['pid'], 'exit_code': manifest['exit_code'],
        'synthetic_ABI_calls': routing['synthetic_ABI_calls'], 'native_XPC_records': len(native),
        'peer_records': sum('peer_metadata' in e for e in native),
        'create_status': decoded['decode']['create_status'] if decoded else None,
        'frames': decoded['output_frames'] if decoded else 0, 'hardware_video_execution_proved': False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'run'])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--dependency-build', type=Path)
    parser.add_argument('--profile', type=Path)
    parser.add_argument('--build', type=Path)
    parser.add_argument('--codec', choices=['H264', 'MPEG2Video'], default='H264')
    parser.add_argument('--mode', choices=['inspect', 'cpu', 'hardware'])
    parser.add_argument('--override', choices=['native', 'wrong-key', 'present-key'], default='native')
    parser.add_argument('--routing', choices=['passive', 'observe'], default='observe')
    parser.add_argument('--peer', choices=['passive', 'observe'], default=None)
    parser.add_argument('--reservation-root', type=Path, default=ROOT)
    args = parser.parse_args()
    args.out.resolve().relative_to(ROOT / 'results')
    if args.action == 'build':
        if not args.dependency_build or not args.profile:
            parser.error('build requires --dependency-build and --profile')
        build(args)
    else:
        if not args.build or not args.mode:
            parser.error('run requires --build and --mode')
        run(args)


if __name__ == '__main__':
    main()
