#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze/build the public-dyld video image observer; do not execute any probe."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fixture', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out, fixture = args.out.resolve(), args.fixture.resolve()
    out.relative_to(ROOT / 'results')
    files = list(fixture.iterdir())
    if len(files) != 13 or not all(p.is_file() and not p.is_symlink()
            and re.fullmatch(r'fixture\.json|frame-\d{3}\.avcc|cpu-frame-\d{3}\.nv12', p.name) for p in files):
        raise ValueError('Expected six AVCC frames, six independent CPU references and fixture.json')
    out.mkdir(exist_ok=False)
    (out / 'assets/fixture').mkdir(parents=True)
    (out / 'runtime').mkdir()
    names = ['video_image_catalog.mm', 'video_image_reception.mm', 'video_image_fixture.c',
             'video_va_observer.mm', 'video_va_reception.mm', 'video_va_vt_client.mm',
             'vda_engine_probe.mm', 'video_engine_probe.mm']
    for name in names:
        shutil.copyfile(ROOT / 'tools' / name, out / name)
    shutil.copyfile(Path(__file__), out / 'builder.py')
    for p in files:
        shutil.copyfile(p, out / 'assets/fixture' / p.name)
    for name, path in {'run_sdk_host.py': ROOT / 'sdk-combined/runtime/run_sdk_host.py',
                       'lab_gpu_reservation.py': ROOT / 'tools/lab_gpu_reservation.py'}.items():
        shutil.copyfile(path, out / 'runtime' / name)
    library, calibration = out / 'libVideoVAObserver.dylib', out / 'libVideoImageFixture.dylib'
    common = ['clang++', '-arch', 'x86_64', '-O2', '-std=c++17', '-fno-objc-arc']
    commands = [
        ('observer', common + ['-dynamiclib', out / 'video_va_observer.mm', '-framework', 'Foundation',
            '-framework', 'IOKit', '-install_name', library, '-o', library]),
        ('sign-observer', ['codesign', '--force', '--sign', '-', library]),
        ('calibration', ['clang', '-arch', 'x86_64', '-O2', '-dynamiclib', out / 'video_image_fixture.c',
            '-install_name', calibration, '-current_version', '1.2.3', '-compatibility_version', '1.0.0',
            '-o', calibration]),
        ('sign-calibration', ['codesign', '--force', '--sign', '-', calibration]),
        ('VDA-client', common + ['-Dmain=KPVDAMain', '-Wno-deprecated-declarations', '-c',
            out / 'vda_engine_probe.mm', '-o', out / 'vda.o']),
        ('VT-client', common + ['-c', out / 'video_va_vt_client.mm', '-o', out / 'vt.o']),
        ('host', common + [out / 'video_image_reception.mm', out / 'video_image_catalog.mm',
            out / 'vda.o', out / 'vt.o', library, '-framework', 'Foundation', '-framework', 'IOKit',
            '-framework', 'VideoDecodeAcceleration', '-framework', 'VideoToolbox', '-framework', 'CoreVideo',
            '-framework', 'CoreMedia', '-framework', 'Metal', '-Wl,-export_dynamic', '-o', out / 'application']),
    ]
    records = []
    for label, argv in commands:
        argv = list(map(str, argv))
        z = subprocess.run(argv, capture_output=True, timeout=60)
        (out / (label + '.stdout')).write_bytes(z.stdout)
        (out / (label + '.stderr')).write_bytes(z.stderr)
        records.append({'label': label, 'argv': argv, 'exit_code': z.returncode})
        (out / 'commands.json').write_text(json.dumps(records, indent=2) + '\n')
        if z.returncode:
            raise RuntimeError(label + ': inspect the retained build stderr')
    configs = {'observer-config.json': {'observer_library_SHA256': sha(library)},
               'image-config.json': {'calibration_library': str(calibration), 'calibration_SHA256': sha(calibration)}}
    for name, value in configs.items():
        (out / 'assets' / name).write_text(json.dumps(value, indent=2) + '\n')
    inputs = {'source_hashes': {n: sha(out / n) for n in names + ['builder.py']},
        'assets_SHA256': {str(p.relative_to(out / 'assets')): sha(p) for p in (out / 'assets').rglob('*') if p.is_file()},
        'runtime_SHA256': {p.name: sha(p) for p in (out / 'runtime').iterdir()},
        'executable_SHA256': sha(out / 'application'), 'observer_library_SHA256': sha(library),
        'calibration_library_SHA256': sha(calibration), 'objects_SHA256': {n: sha(out / n) for n in ['vda.o', 'vt.o']},
        'GPU_execution': False, 'scope': 'Process-local public dyld metadata; no-call private symbol lookup'}
    (out / 'inputs.json').write_text(json.dumps(inputs, indent=2) + '\n')
    print(json.dumps({'status': 'BUILT', 'GPU_work': 0, 'source_files': len(names)}))


if __name__ == '__main__':
    main()
