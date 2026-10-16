#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Test both public hardware flags without rebuilding qualified entry/metadata code."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def check(parent, inputs):
    for folder, key in [('', 'source_hashes'), ('assets', 'assets_SHA256'), ('runtime', 'runtime_SHA256')]:
        for name, digest in inputs[key].items():
            if sha(parent / folder / name) != digest:
                raise ValueError('Changed metadata-build input: ' + name)
    for name, digest in inputs['object_SHA256'].items():
        if sha(parent / name) != digest:
            raise ValueError('Reused native object changed')
    if sha(parent / 'libVideoRegistryMetadata.dylib') != inputs['metadata_library_SHA256'] \
            or sha(inputs['qualified_entry_library']) != inputs['qualified_entry_library_SHA256']:
        raise ValueError('Qualified linked library changed')


def build(args):
    parent, out = args.metadata_build.resolve(), args.out.resolve()
    inputs = json.loads((parent / 'inputs.json').read_text())
    check(parent, inputs)
    out.mkdir(exist_ok=False)
    shutil.copytree(parent / 'assets', out / 'assets')
    shutil.copytree(parent / 'runtime', out / 'runtime')
    names = []
    for name in inputs['source_hashes']:
        target = 'metadata-builder.py' if name == 'builder.py' else name
        shutil.copyfile(parent / name, out / target)
        names.append(target)
    for name, source in [('video_registry_spec.mm', ROOT / 'tools/video_registry_spec.mm'),
                         ('builder.py', Path(__file__))]:
        shutil.copyfile(source, out / name)
        names.append(name)
    shutil.copyfile(parent / 'inputs.json', out / 'metadata-inputs.json')
    common = ['clang++', '-arch', 'x86_64', '-O2', '-std=c++17', '-fno-objc-arc']
    records = []
    libraries, variants = {}, {}
    for kind, flag in [('passive', '0'), ('both', '1')]:
        library = out / ('libVideoRegistrySpec-' + kind + '.dylib')
        commands = [(kind + '-library', common + ['-dynamiclib', '-DKPREG_SPEC_BOTH=' + flag,
            out / 'video_registry_spec.mm', '-framework', 'Foundation', '-framework', 'CoreMedia',
            '-framework', 'VideoToolbox',
            '-install_name', library, '-o', library]),
            ('sign-' + kind, ['codesign', '--force', '--sign', '-', library])]
        for codec in ['H264', 'MPEG2Video']:
            variant = codec + '-' + kind
            commands.append((variant, common + [parent / 'base-codec-host.o', parent / 'base-catalog.o',
                parent / (codec + '.o'), library, parent / 'libVideoRegistryMetadata.dylib',
                inputs['qualified_entry_library'], '-framework', 'Foundation', '-framework', 'CoreMedia',
                '-framework', 'VideoToolbox', '-framework', 'CoreVideo', '-framework', 'Metal',
                '-o', out / ('application-' + variant)]))
        for label, argv in commands:
            argv = list(map(str, argv))
            q = subprocess.run(argv, capture_output=True, timeout=60)
            (out / (label + '.stdout')).write_bytes(q.stdout)
            (out / (label + '.stderr')).write_bytes(q.stderr)
            records.append({'label': label, 'argv': argv, 'exit_code': q.returncode})
            write(out / 'commands.json', records)
            if q.returncode:
                raise RuntimeError(label + ': inspect retained stderr')
        libraries[kind] = sha(library)
        for codec in ['H264', 'MPEG2Video']:
            variants[codec + '-' + kind] = sha(out / ('application-' + codec + '-' + kind))
    write(out / 'inputs.json', {
        'source_hashes': {n: sha(out / n) for n in names},
        'assets_SHA256': {str(p.relative_to(out / 'assets')): sha(p) for p in (out / 'assets').rglob('*') if p.is_file()},
        'runtime_SHA256': {p.name: sha(p) for p in (out / 'runtime').iterdir()},
        'metadata_build': str(parent), 'metadata_inputs_SHA256': sha(parent / 'inputs.json'),
        'qualified_entry_library_SHA256': inputs['qualified_entry_library_SHA256'],
        'qualified_metadata_library_SHA256': inputs['metadata_library_SHA256'],
        'specification_library_SHA256': libraries, 'executable_variants_SHA256': variants,
        'GPU_execution': False, 'private_function_invoked_by_host': False})
    print(json.dumps({'status': 'BUILT', 'variants': 4, 'GPU_work': 0}))


def run(args):
    b, out = args.build.resolve(), args.out.resolve()
    inputs = json.loads((b / 'inputs.json').read_text())
    for folder, key in [('', 'source_hashes'), ('assets', 'assets_SHA256'), ('runtime', 'runtime_SHA256')]:
        for name, digest in inputs[key].items():
            if sha(b / folder / name) != digest:
                raise ValueError('Frozen input changed: ' + name)
    parent = Path(inputs['metadata_build'])
    if sha(parent / 'inputs.json') != inputs['metadata_inputs_SHA256']:
        raise ValueError('Metadata manifest changed')
    check(parent, json.loads((parent / 'inputs.json').read_text()))
    for kind, digest in inputs['specification_library_SHA256'].items():
        if sha(b / ('libVideoRegistrySpec-' + kind + '.dylib')) != digest:
            raise ValueError('Specification library changed')
    binary = b / ('application-' + args.variant)
    expected = inputs['executable_variants_SHA256'][args.variant]
    if sha(binary) != expected:
        raise ValueError('Executable changed')
    out.mkdir(exist_ok=False)
    (out / 'outputs').mkdir()
    shutil.copytree(b / 'assets', out / 'assets')
    for name in inputs['source_hashes']:
        shutil.copyfile(b / name, out / name)
    shutil.copyfile(binary, out / 'application')
    (out / 'application').chmod(0o755)
    write(out / 'inputs.json', {**inputs, 'executable_SHA256': expected, 'selected_variant': args.variant})
    shutil.copyfile(Path(__file__), out / 'runner.py')
    sys.path.insert(0, str(b / 'runtime'))
    from run_sdk_host import run_host
    manifest = run_host(out / 'application', out / 'execution',
        [str(out / 'assets'), str(out / 'outputs'), args.mode], args.reservation_root.resolve())
    result = json.loads((out / 'execution/execution.stdout').read_text())
    write(out / 'results.json', result)
    for name in ['images.json', 'metadata.json', 'specification.json']:
        shutil.copyfile(out / 'outputs' / name, out / name)
    specification = json.loads((out / 'specification.json').read_text())
    if not specification['hardware_requirement_preserved']:
        raise ValueError('Hardware requirement changed')
    check(parent, json.loads((parent / 'inputs.json').read_text()))
    decoded = result['public_decode']
    print(json.dumps({'status': 'PROCESS_COMPLETED', 'variant': args.variant, 'mode': args.mode,
        'pid': manifest['pid'], 'exit_code': manifest['exit_code'], 'both_flags_applied': specification['applied'],
        'create_status': decoded['decode']['create_status'], 'frames': decoded['output_frames'],
        'hardware_video_execution_proved': False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'run'])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--metadata-build', type=Path)
    parser.add_argument('--build', type=Path)
    parser.add_argument('--variant', choices=['H264-passive', 'H264-both', 'MPEG2Video-passive', 'MPEG2Video-both'])
    parser.add_argument('--mode', choices=['cpu', 'hardware'])
    parser.add_argument('--reservation-root', type=Path, default=ROOT)
    args = parser.parse_args()
    args.out.resolve().relative_to(ROOT / 'results')
    if args.action == 'build':
        if not args.metadata_build:
            parser.error('build requires --metadata-build')
        build(args)
    else:
        if not all([args.build, args.variant, args.mode]):
            parser.error('run requires --build, --variant and --mode')
        run(args)


if __name__ == '__main__':
    main()
