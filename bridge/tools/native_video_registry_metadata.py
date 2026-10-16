#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Add public-CF metadata observation while reusing the exact qualified host/library."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
NEW = ['video_registry_metadata.h', 'video_registry_metadata.mm', 'video_registry_metadata_decoder.mm']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def verify_base(base, inputs):
    for folder, key in [('', 'source_hashes'), ('assets', 'assets_SHA256'), ('runtime', 'runtime_SHA256')]:
        for name, digest in inputs[key].items():
            if sha(base / folder / name) != digest:
                raise ValueError('Changed base input: ' + name)
    for name, digest in inputs['object_SHA256'].items():
        if sha(base / name) != digest:
            raise ValueError('Changed qualified object')
    for kind, digest in inputs['library_SHA256'].items():
        if sha(base / ('libVideoRegistry-' + kind + '.dylib')) != digest:
            raise ValueError('Changed qualified library')


def build(args):
    base, out = args.base_build.resolve(), args.out.resolve()
    inputs = json.loads((base / 'inputs.json').read_text())
    verify_base(base, inputs)
    out.mkdir(exist_ok=False)
    shutil.copytree(base / 'assets', out / 'assets')
    shutil.copytree(base / 'runtime', out / 'runtime')
    names = []
    for name in inputs['source_hashes']:
        target = 'base-builder.py' if name == 'builder.py' else name
        shutil.copyfile(base / name, out / target)
        names.append(target)
    for name in NEW:
        shutil.copyfile(ROOT / 'tools' / name, out / name)
        names.append(name)
    shutil.copyfile(Path(__file__), out / 'builder.py')
    names.append('builder.py')
    shutil.copyfile(base / 'inputs.json', out / 'base-inputs.json')
    for source, target in [('codec-host.o', 'base-codec-host.o'), ('catalog.o', 'base-catalog.o')]:
        shutil.copyfile(base / source, out / target)
    library, original = out / 'libVideoRegistryMetadata.dylib', base / 'libVideoRegistry-observer.dylib'
    common = ['clang++', '-arch', 'x86_64', '-O2', '-std=c++17', '-fno-objc-arc',
              '-fno-omit-frame-pointer', '-Wno-deprecated-declarations', '-Wno-frame-address']
    commands = [
        ('metadata-library', common + ['-dynamiclib', out / 'video_registry_metadata.mm', '-framework', 'Foundation',
            '-install_name', library, '-o', library]),
        ('sign-metadata', ['codesign', '--force', '--sign', '-', library])]
    for codec, flag in [('H264', '0'), ('MPEG2Video', '1')]:
        obj = out / (codec + '.o')
        commands += [(codec + '-metadata-decoder', common + ['-DKPREG_MPEG2=' + flag, '-c',
            out / 'video_registry_metadata_decoder.mm', '-o', obj]),
            (codec + '-host', common + [out / 'base-codec-host.o', out / 'base-catalog.o', obj, library, original,
                '-framework', 'Foundation', '-framework', 'CoreMedia', '-framework', 'VideoToolbox',
                '-framework', 'CoreVideo', '-framework', 'Metal', '-o', out / ('application-' + codec)])]
    records = []
    for label, argv in commands:
        argv = list(map(str, argv))
        started = time.monotonic()
        result = subprocess.run(argv, capture_output=True, timeout=60)
        (out / (label + '.stdout')).write_bytes(result.stdout)
        (out / (label + '.stderr')).write_bytes(result.stderr)
        records.append({'label': label, 'argv': argv, 'exit_code': result.returncode,
                        'diagnostic_build_seconds': time.monotonic() - started})
        write(out / 'commands.json', records)
        if result.returncode:
            raise RuntimeError(label + ': inspect retained stderr')
    config = json.loads((out / 'assets/registry-config.json').read_text())
    config['metadata_library_SHA256'] = sha(library)
    write(out / 'assets/registry-config.json', config)
    write(out / 'inputs.json', {
        'source_hashes': {name: sha(out / name) for name in names},
        'assets_SHA256': {str(p.relative_to(out / 'assets')): sha(p) for p in (out / 'assets').rglob('*') if p.is_file()},
        'runtime_SHA256': {p.name: sha(p) for p in (out / 'runtime').iterdir()},
        'executable_variants_SHA256': {c: sha(out / ('application-' + c)) for c in ['H264', 'MPEG2Video']},
        'base_build': str(base), 'base_inputs_SHA256': sha(base / 'inputs.json'),
        'qualified_entry_library': str(original), 'qualified_entry_library_SHA256': sha(original),
        'qualified_tail_object_SHA256': inputs['object_SHA256']['tail.o'],
        'reused_host_object_SHA256': sha(out / 'base-codec-host.o'),
        'reused_catalog_object_SHA256': sha(out / 'base-catalog.o'),
        'metadata_library_SHA256': sha(library), 'object_SHA256': {p.name: sha(p) for p in out.glob('*.o')},
        'GPU_execution': False, 'private_function_invoked_by_host': False})
    print(json.dumps({'status': 'BUILT', 'variants': 2, 'qualified_entry_library_reused': True,
                      'qualified_host_object_reused': True, 'GPU_work': 0}))


def run(args):
    b, out = args.build.resolve(), args.out.resolve()
    inputs = json.loads((b / 'inputs.json').read_text())
    for folder, key in [('', 'source_hashes'), ('assets', 'assets_SHA256'), ('runtime', 'runtime_SHA256')]:
        for name, digest in inputs[key].items():
            if sha(b / folder / name) != digest:
                raise ValueError('Changed frozen input: ' + name)
    base = Path(inputs['base_build'])
    if sha(base / 'inputs.json') != inputs['base_inputs_SHA256']:
        raise ValueError('Changed base manifest')
    verify_base(base, json.loads((base / 'inputs.json').read_text()))
    if sha(b / 'libVideoRegistryMetadata.dylib') != inputs['metadata_library_SHA256']:
        raise ValueError('Metadata library changed')
    binary = b / ('application-' + args.codec)
    expected = inputs['executable_variants_SHA256'][args.codec]
    if sha(binary) != expected:
        raise ValueError('Frozen executable changed')
    out.mkdir(exist_ok=False)
    (out / 'outputs').mkdir()
    shutil.copytree(b / 'assets', out / 'assets')
    for name in inputs['source_hashes']:
        shutil.copyfile(b / name, out / name)
    shutil.copyfile(binary, out / 'application')
    (out / 'application').chmod(0o755)
    write(out / 'inputs.json', {**inputs, 'executable_SHA256': expected, 'selected_codec': args.codec})
    shutil.copyfile(Path(__file__), out / 'runner.py')
    sys.path.insert(0, str(b / 'runtime'))
    from run_sdk_host import run_host
    manifest = run_host(out / 'application', out / 'execution',
        [str(out / 'assets'), str(out / 'outputs'), args.mode], args.reservation_root.resolve())
    result = json.loads((out / 'execution/execution.stdout').read_text())
    write(out / 'results.json', result)
    shutil.copyfile(out / 'outputs/images.json', out / 'images.json')
    metadata = json.loads((out / 'outputs/metadata.json').read_text())
    write(out / 'metadata.json', metadata)
    if sha(b / 'libVideoRegistryMetadata.dylib') != inputs['metadata_library_SHA256'] \
            or sha(inputs['qualified_entry_library']) != inputs['qualified_entry_library_SHA256']:
        raise ValueError('Native dependency changed during observation')
    decoded = result['public_decode']
    print(json.dumps({'status': 'PROCESS_COMPLETED', 'codec': args.codec, 'mode': args.mode,
        'pid': manifest['pid'], 'exit_code': manifest['exit_code'], 'metadata_events': len(metadata['events']),
        'public_retain_control_valid': metadata['public_retain_control_valid'],
        'create_status': decoded['decode']['create_status'], 'frames': decoded['output_frames'],
        'hardware_video_execution_proved': False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'run'])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--base-build', type=Path)
    parser.add_argument('--build', type=Path)
    parser.add_argument('--codec', choices=['H264', 'MPEG2Video'])
    parser.add_argument('--mode', choices=['cpu', 'hardware'])
    parser.add_argument('--reservation-root', type=Path, default=ROOT)
    args = parser.parse_args()
    args.out.resolve().relative_to(ROOT / 'results')
    if args.action == 'build':
        if not args.base_build:
            parser.error('build requires --base-build')
        build(args)
    else:
        if not all([args.build, args.codec, args.mode]):
            parser.error('run requires --build, --codec and --mode')
        run(args)


if __name__ == '__main__':
    main()
