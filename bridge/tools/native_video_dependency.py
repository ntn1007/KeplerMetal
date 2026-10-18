#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build/run a pinned public IORegistry observer, reusing qualified codec objects."""
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


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def verify(parent):
    data = json.loads((parent / 'inputs.json').read_text())
    for folder, key in [('', 'source_hashes'), ('assets', 'assets_SHA256'), ('runtime', 'runtime_SHA256')]:
        for name, digest in data[key].items():
            if sha(parent / folder / name) != digest:
                raise ValueError('Qualified metadata input changed: ' + name)
    for name, digest in data['object_SHA256'].items():
        if sha(parent / name) != digest:
            raise ValueError('Qualified object changed: ' + name)
    if sha(parent / 'libVideoRegistryMetadata.dylib') != data['metadata_library_SHA256'] \
            or sha(data['qualified_entry_library']) != data['qualified_entry_library_SHA256']:
        raise ValueError('Qualified library changed')
    return data


def build(args):
    parent, out = args.metadata_build.resolve(), args.out.resolve()
    original = verify(parent)
    profile = json.loads(args.profile.read_text())
    if profile['UUID'] != 'e7231bea63883d0a95c0a93ce970b96b' \
            or profile['IORegistry_search_return_offset'] != 6285217 or len(profile['functions']) != 5:
        raise ValueError('Inspected dependency profile required')
    out.mkdir(exist_ok=False)
    shutil.copytree(parent / 'assets', out / 'assets')
    shutil.copytree(parent / 'runtime', out / 'runtime')
    shutil.copyfile(args.profile, out / 'assets/dependency-profile.json')
    write(out / 'assets/dependency-choice.json', {'mode': 'native'})
    shutil.copyfile(parent / 'inputs.json', out / 'metadata-inputs.json')
    names = []
    for name in original['source_hashes']:
        target = 'metadata-builder.py' if name == 'builder.py' else name
        shutil.copyfile(parent / name, out / target)
        names.append(target)
    for name in ['video_dependency.h', 'video_dependency.mm', 'video_dependency_inspect.mm']:
        shutil.copyfile(ROOT / 'tools' / name, out / name)
        names.append(name)
    shutil.copyfile(Path(__file__), out / 'builder.py')
    names.append('builder.py')
    common = ['clang++', '-arch', 'x86_64', '-O2', '-std=c++17', '-fno-objc-arc', '-Wno-deprecated-declarations']
    frameworks = ['-framework', 'Foundation', '-framework', 'CoreMedia', '-framework', 'VideoToolbox',
                  '-framework', 'CoreVideo', '-framework', 'Metal', '-framework', 'IOKit']
    commands = []
    for kind, record, enable in [('passive', 0, 0), ('observer', 1, 0), ('both', 1, 1)]:
        library = out / ('libVideoDependency-' + kind + '.dylib')
        commands += [(kind + '-library', common + ['-dynamiclib', '-DKPDEP_RECORD=' + str(record),
            '-DKPDEP_ENABLE=' + str(enable), out / 'video_dependency.mm', *frameworks,
            '-install_name', library, '-o', library]),
            ('sign-' + kind, ['codesign', '--force', '--sign', '-', library])]
        for codec in ['H264', 'MPEG2Video']:
            commands.append((codec + '-' + kind, common + [parent / 'base-codec-host.o', parent / 'base-catalog.o',
                parent / (codec + '.o'), library, parent / 'libVideoRegistryMetadata.dylib',
                original['qualified_entry_library'], *frameworks, '-o', out / ('application-' + codec + '-' + kind)]))
    commands.append(('inspect', common + [out / 'video_dependency_inspect.mm', parent / 'base-catalog.o',
        out / 'libVideoDependency-observer.dylib', *frameworks, '-o', out / 'application-inspect']))
    records = []
    for label, argv in commands:
        argv = list(map(str, argv))
        start = time.monotonic()
        q = subprocess.run(argv, capture_output=True, timeout=60)
        (out / (label + '.stdout')).write_bytes(q.stdout)
        (out / (label + '.stderr')).write_bytes(q.stderr)
        records.append({'label': label, 'argv': argv, 'exit_code': q.returncode,
                        'diagnostic_build_seconds': time.monotonic() - start})
        write(out / 'commands.json', records)
        if q.returncode:
            raise RuntimeError(label + ': inspect retained stderr')
    libraries = {kind: sha(out / ('libVideoDependency-' + kind + '.dylib')) for kind in ['passive', 'observer', 'both']}
    write(out / 'assets/dependency-config.json', {'libraries': libraries, 'profile_SHA256': sha(out / 'assets/dependency-profile.json')})
    variants = ['inspect'] + [c + '-' + k for c in ['H264', 'MPEG2Video'] for k in libraries]
    write(out / 'inputs.json', {
        'source_hashes': {name: sha(out / name) for name in names},
        'assets_SHA256': {str(p.relative_to(out / 'assets')): sha(p) for p in (out / 'assets').rglob('*') if p.is_file()},
        'runtime_SHA256': {p.name: sha(p) for p in (out / 'runtime').iterdir()},
        'metadata_build': str(parent), 'metadata_inputs_SHA256': sha(parent / 'inputs.json'),
        'qualified_metadata_library_SHA256': original['metadata_library_SHA256'],
        'qualified_entry_library_SHA256': original['qualified_entry_library_SHA256'],
        'reused_host_object_SHA256': sha(parent / 'base-codec-host.o'),
        'reused_catalog_object_SHA256': sha(parent / 'base-catalog.o'),
        'reused_decoder_objects_SHA256': {c: sha(parent / (c + '.o')) for c in ['H264', 'MPEG2Video']},
        'dependency_libraries_SHA256': libraries,
        'executable_variants_SHA256': {v: sha(out / ('application-' + v)) for v in variants},
        'GPU_execution': False, 'unknown_private_function_invoked_by_host': False})
    print(json.dumps({'status': 'BUILT', 'variants': len(variants), 'qualified_objects_reused': True, 'GPU_work': 0}))


def run(args):
    build_root, out = args.build.resolve(), args.out.resolve()
    data = json.loads((build_root / 'inputs.json').read_text())
    for folder, key in [('', 'source_hashes'), ('assets', 'assets_SHA256'), ('runtime', 'runtime_SHA256')]:
        for name, digest in data[key].items():
            if sha(build_root / folder / name) != digest:
                raise ValueError('Frozen dependency input changed: ' + name)
    parent = Path(data['metadata_build'])
    if sha(parent / 'inputs.json') != data['metadata_inputs_SHA256']:
        raise ValueError('Qualified metadata manifest changed')
    verify(parent)
    for kind, digest in data['dependency_libraries_SHA256'].items():
        if sha(build_root / ('libVideoDependency-' + kind + '.dylib')) != digest:
            raise ValueError('Dependency library changed')
    if (args.variant == 'inspect') != (args.mode == 'inspect'):
        raise ValueError('Inspect variant never creates a decoder')
    if args.override != 'native' and (args.variant != 'H264-both' or args.mode != 'hardware'):
        raise ValueError('Counterfactual is restricted to H264-both hardware')
    binary = build_root / ('application-' + args.variant)
    expected = data['executable_variants_SHA256'][args.variant]
    if sha(binary) != expected:
        raise ValueError('Executable changed')
    out.mkdir(exist_ok=False)
    (out / 'outputs').mkdir()
    shutil.copytree(build_root / 'assets', out / 'assets')
    write(out / 'assets/dependency-choice.json', {'mode': args.override})
    for name in data['source_hashes']:
        shutil.copyfile(build_root / name, out / name)
    shutil.copyfile(Path(__file__), out / 'runner.py')
    shutil.copyfile(binary, out / 'application')
    (out / 'application').chmod(0o755)
    run_assets = dict(data['assets_SHA256'])
    run_assets['dependency-choice.json'] = sha(out / 'assets/dependency-choice.json')
    write(out / 'inputs.json', {**data, 'assets_SHA256': run_assets, 'selected_variant': args.variant,
        'executable_SHA256': expected, 'override_mode': args.override})
    sys.path.insert(0, str(build_root / 'runtime'))
    from run_sdk_host import run_host
    manifest = run_host(out / 'application', out / 'execution',
        [str(out / 'assets'), str(out / 'outputs'), args.mode], args.reservation_root.resolve())
    result = json.loads((out / 'execution/execution.stdout').read_text())
    write(out / 'results.json', result)
    for filename in ['images.json', 'dependency.json'] + ([] if args.mode == 'inspect' else ['metadata.json']):
        shutil.copyfile(out / 'outputs' / filename, out / filename)
    dependency = json.loads((out / 'dependency.json').read_text())
    if dependency['status'] != 'COMPLETE' or not dependency['public_query_controls_valid']:
        raise ValueError('Incomplete dependency observation')
    verify(parent)
    decoded = result.get('public_decode')
    print(json.dumps({'status': 'PROCESS_COMPLETED', 'variant': args.variant, 'mode': args.mode,
        'PID': manifest['pid'], 'exit_code': manifest['exit_code'], 'public_query_controls_valid': True,
        'native_property_queries': sum(not e['synthetic_control'] for e in dependency['events']),
        'create_status': decoded['decode']['create_status'] if decoded else None,
        'frames': decoded['output_frames'] if decoded else 0, 'hardware_video_execution_proved': False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'run'])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--metadata-build', type=Path)
    parser.add_argument('--profile', type=Path)
    parser.add_argument('--build', type=Path)
    parser.add_argument('--variant', choices=['inspect'] + [c + '-' + k for c in ['H264', 'MPEG2Video'] for k in ['passive', 'observer', 'both']])
    parser.add_argument('--mode', choices=['inspect', 'cpu', 'hardware'])
    parser.add_argument('--override', choices=['native', 'wrong-key', 'present-key'], default='native')
    parser.add_argument('--reservation-root', type=Path, default=ROOT)
    args = parser.parse_args()
    args.out.resolve().relative_to(ROOT / 'results')
    if args.action == 'build':
        if not args.metadata_build or not args.profile:
            parser.error('build requires --metadata-build and --profile')
        build(args)
    else:
        if not all([args.build, args.variant, args.mode]):
            parser.error('run requires --build, --variant and --mode')
        run(args)


if __name__ == '__main__':
    main()
