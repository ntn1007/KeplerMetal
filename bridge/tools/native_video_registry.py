#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze/build/run the bounded CoreMedia entry observer and its CPU controls.

One assembler object is shared by calibration, plain and observer libraries.
All codec hosts share one host object. No system installation or GPU dispatch
occurs while building. Unknown private functions are never called by the host.
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
SOURCES = ['video_registry_layout.h', 'video_registry_tail.S', 'video_registry_observer.h',
           'video_registry_observer.mm', 'video_registry_client.mm', 'video_registry_decoder.mm',
           'video_image_catalog.mm', 'video_va_vt_client.mm', 'video_mpeg2_vt_client.mm', 'video_engine_probe.mm']
VARIANTS = ['calibration', 'H264-plain', 'H264-observer', 'MPEG2Video-plain', 'MPEG2Video-observer']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def build(args):
    out = args.out.resolve()
    profile = json.loads(args.profile.read_text())
    if profile['UUID'] != '7c4ae5aed528396982c6a4a534949ef3' or len(profile['symbols']) != 6:
        raise ValueError('Unexpected inspected CoreMedia profile')
    fixtures = {'H264': args.h264.resolve(), 'MPEG2Video': args.mpeg2.resolve()}
    for codec, folder in fixtures.items():
        extension = 'avcc' if codec == 'H264' else 'm2v'
        files = list(folder.iterdir())
        if len(files) != 13 or not all(p.is_file() and not p.is_symlink() and re.fullmatch(
                r'fixture\.json|frame-\d{3}\.' + extension + r'|cpu-frame-\d{3}\.nv12', p.name) for p in files):
            raise ValueError('Thirteen-file independent fixture required for ' + codec)
    out.mkdir(exist_ok=False)
    (out / 'assets/fixtures').mkdir(parents=True)
    (out / 'runtime').mkdir()
    for name in SOURCES:
        shutil.copyfile(ROOT / 'tools' / name, out / name)
    shutil.copyfile(Path(__file__), out / 'builder.py')
    shutil.copyfile(args.profile, out / 'assets/registry-profile.json')
    for codec, folder in fixtures.items():
        shutil.copytree(folder, out / 'assets/fixtures' / codec)
    for name, path in {'run_sdk_host.py': ROOT / 'sdk-combined/runtime/run_sdk_host.py',
                       'lab_gpu_reservation.py': ROOT / 'tools/lab_gpu_reservation.py'}.items():
        shutil.copyfile(path, out / 'runtime' / name)
    common = ['clang++', '-arch', 'x86_64', '-O2', '-std=c++17', '-fno-objc-arc',
              '-Wno-deprecated-declarations']
    commands = [('tail-object', ['clang', '-arch', 'x86_64', '-c', out / 'video_registry_tail.S', '-o', out / 'tail.o']),
        ('catalog-object', common + ['-c', out / 'video_image_catalog.mm', '-o', out / 'catalog.o'])]
    for kind in ['observer', 'plain', 'calibration']:
        defines = ['-DKPREG_INTERPOSE=' + ('1' if kind == 'observer' else '0'),
                   '-DKPREG_CALIBRATION=' + ('1' if kind == 'calibration' else '0')]
        obj, library = out / ('observer-' + kind + '.o'), out / ('libVideoRegistry-' + kind + '.dylib')
        commands += [(kind + '-object', common + defines + ['-c', out / 'video_registry_observer.mm', '-o', obj]),
            (kind + '-library', common + ['-dynamiclib', obj, out / 'tail.o', '-framework', 'Foundation',
                '-framework', 'CoreMedia', '-Wl,-undefined,dynamic_lookup', '-install_name', library, '-o', library]),
            ('sign-' + kind, ['codesign', '--force', '--sign', '-', library])]
    commands += [
        ('calibration-client', common + ['-DKPREG_CALIBRATION=1', '-c', out / 'video_registry_client.mm', '-o', out / 'calibration-host.o']),
        ('codec-client', common + ['-DKPREG_CALIBRATION=0', '-c', out / 'video_registry_client.mm', '-o', out / 'codec-host.o']),
        ('H264-decoder', common + ['-DKPREG_MPEG2=0', '-c', out / 'video_registry_decoder.mm', '-o', out / 'H264.o']),
        ('MPEG2-decoder', common + ['-DKPREG_MPEG2=1', '-c', out / 'video_registry_decoder.mm', '-o', out / 'MPEG2Video.o']),
        ('calibration-host', common + [out / 'calibration-host.o', out / 'catalog.o',
            out / 'libVideoRegistry-calibration.dylib', '-framework', 'Foundation', '-framework', 'CoreMedia',
            '-o', out / 'application-calibration'])]
    for codec in ['H264', 'MPEG2Video']:
        for kind in ['plain', 'observer']:
            commands.append((codec + '-' + kind, common + [out / 'codec-host.o', out / 'catalog.o', out / (codec + '.o'),
                out / ('libVideoRegistry-' + kind + '.dylib'), '-framework', 'Foundation', '-framework', 'CoreMedia',
                '-framework', 'VideoToolbox', '-framework', 'CoreVideo', '-framework', 'Metal',
                '-o', out / ('application-' + codec + '-' + kind)]))
    records = []
    for label, argv in commands:
        argv = list(map(str, argv))
        started = time.monotonic()
        child = subprocess.run(argv, capture_output=True, timeout=60)
        (out / (label + '.stdout')).write_bytes(child.stdout)
        (out / (label + '.stderr')).write_bytes(child.stderr)
        records.append({'label': label, 'argv': argv, 'exit_code': child.returncode,
                        'diagnostic_build_seconds': time.monotonic() - started})
        write(out / 'commands.json', records)
        if child.returncode:
            raise RuntimeError(label + ': inspect retained build stderr')
    libraries = {kind: sha(out / ('libVideoRegistry-' + kind + '.dylib')) for kind in ['observer', 'plain', 'calibration']}
    write(out / 'assets/registry-config.json', {'library_SHA256': libraries,
          'profile_SHA256': sha(out / 'assets/registry-profile.json')})
    write(out / 'inputs.json', {
        'source_hashes': {name: sha(out / name) for name in SOURCES + ['builder.py']},
        'assets_SHA256': {str(p.relative_to(out / 'assets')): sha(p) for p in (out / 'assets').rglob('*') if p.is_file()},
        'runtime_SHA256': {p.name: sha(p) for p in (out / 'runtime').iterdir()},
        'library_SHA256': libraries, 'object_SHA256': {p.name: sha(p) for p in out.glob('*.o')},
        'executable_variants_SHA256': {v: sha(out / ('application-' + v)) for v in VARIANTS},
        'GPU_execution': False, 'shared_tail_object': 'tail.o', 'shared_actual_host_object': 'codec-host.o',
        'private_function_invoked_by_host': False})
    print(json.dumps({'status': 'BUILT', 'variants': len(VARIANTS), 'GPU_work': 0,
                      'shared_tail_object_SHA256': sha(out / 'tail.o')}))


def run(args):
    build_root, out = args.build.resolve(), args.out.resolve()
    inputs = json.loads((build_root / 'inputs.json').read_text())
    for folder, key in [('', 'source_hashes'), ('assets', 'assets_SHA256'), ('runtime', 'runtime_SHA256')]:
        for name, digest in inputs[key].items():
            if sha(build_root / folder / name) != digest:
                raise ValueError('Changed frozen input: ' + name)
    for kind, digest in inputs['library_SHA256'].items():
        if sha(build_root / ('libVideoRegistry-' + kind + '.dylib')) != digest:
            raise ValueError('Observer dependency changed')
    source = build_root / ('application-' + args.variant)
    expected = inputs['executable_variants_SHA256'][args.variant]
    if sha(source) != expected:
        raise ValueError('Frozen executable changed')
    calibration_modes = ['integer', 'floating', 'aggregate', 'mixed', 'variadic', 'flags', 'overflow', 'disabled']
    if (args.variant == 'calibration') != (args.mode in calibration_modes):
        raise ValueError('Calibration modes are isolated from actual framework interposition')
    out.mkdir(exist_ok=False)
    (out / 'outputs').mkdir()
    shutil.copytree(build_root / 'assets', out / 'assets')
    for name in inputs['source_hashes']:
        shutil.copyfile(build_root / name, out / name)
    shutil.copyfile(source, out / 'application')
    (out / 'application').chmod(0o755)
    run_inputs = {**inputs, 'executable_SHA256': expected, 'selected_variant': args.variant}
    write(out / 'inputs.json', run_inputs)
    shutil.copyfile(Path(__file__), out / 'runner.py')
    sys.path.insert(0, str(build_root / 'runtime'))
    from run_sdk_host import run_host
    manifest = run_host(out / 'application', out / 'execution',
        [str(out / 'assets'), str(out / 'outputs'), args.mode], args.reservation_root.resolve())
    result = json.loads((out / 'execution/execution.stdout').read_text())
    write(out / 'results.json', result)
    shutil.copyfile(out / 'outputs/images.json', out / 'images.json')
    for kind, digest in inputs['library_SHA256'].items():
        if sha(build_root / ('libVideoRegistry-' + kind + '.dylib')) != digest:
            raise ValueError('Library changed during observation')
    trace = result.get('trace', {})
    decoded = result.get('public_decode')
    print(json.dumps({'status': 'PROCESS_COMPLETED', 'variant': args.variant, 'mode': args.mode,
        'pid': manifest['pid'], 'exit_code': manifest['exit_code'], 'trace_calls': trace.get('calls'),
        'dropped': trace.get('dropped'), 'verified_CPU_calls': result.get('verified_calls'),
        'decode_create_status': decoded['decode']['create_status'] if decoded else None,
        'output_frames': decoded['output_frames'] if decoded else 0, 'hardware_video_execution_proved': False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'run'])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--profile', type=Path)
    parser.add_argument('--h264', type=Path)
    parser.add_argument('--mpeg2', type=Path)
    parser.add_argument('--build', type=Path)
    parser.add_argument('--variant', choices=VARIANTS)
    parser.add_argument('--mode', choices=['integer', 'floating', 'aggregate', 'mixed', 'variadic', 'flags',
                                        'overflow', 'disabled', 'inspect', 'cpu', 'hardware'])
    parser.add_argument('--reservation-root', type=Path, default=ROOT)
    args = parser.parse_args()
    args.out.resolve().relative_to(ROOT / 'results')
    if args.action == 'build':
        if not all([args.profile, args.h264, args.mpeg2]):
            parser.error('build requires --profile, --h264 and --mpeg2')
        build(args)
    else:
        if not all([args.build, args.variant, args.mode]):
            parser.error('run requires --build, --variant and --mode')
        run(args)


if __name__ == '__main__':
    main()
