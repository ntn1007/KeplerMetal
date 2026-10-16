#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build an isolated VDA client and ABI-preserving own-process observer.

No installer, vendor factory or GPU workload is invoked by this builder.
"""
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
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--fixture', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.relative_to(ROOT / 'results')
    fixture = args.fixture.resolve()
    files = list(fixture.iterdir())
    assert files and all(p.is_file() and not p.is_symlink() for p in files)
    assert all(re.fullmatch(r'fixture\.json|frame-\d{3}\.avcc|cpu-frame-\d{3}\.nv12', p.name) for p in files)
    runtime = {'run_sdk_host.py': ROOT / 'sdk-combined/runtime/run_sdk_host.py',
               'lab_gpu_reservation.py': ROOT / 'tools/lab_gpu_reservation.py'}
    assert all(p.is_file() for p in runtime.values())
    out.mkdir(exist_ok=False)
    (out / 'assets/fixture').mkdir(parents=True)
    (out / 'runtime').mkdir()
    sources = ['video_va_observer.mm', 'video_va_reception.mm', 'vda_engine_probe.mm',
               'video_va_vt_client.mm', 'video_engine_probe.mm']
    for name in sources:
        shutil.copyfile(ROOT / 'tools' / name, out / name)
    shutil.copyfile(Path(__file__), out / 'builder.py')
    for p in files:
        shutil.copyfile(p, out / 'assets/fixture' / p.name)
    for name, path in runtime.items():
        shutil.copyfile(path, out / 'runtime' / name)
    library = out / 'libVideoVAObserver.dylib'
    common = ['clang++', '-arch', 'x86_64', '-O2', '-std=c++17', '-fno-objc-arc']
    commands = [
        ('observer', common + ['-dynamiclib', out / sources[0], '-framework', 'Foundation', '-framework', 'IOKit',
                              '-install_name', library, '-o', library]),
        ('sign-observer', ['codesign', '--force', '--sign', '-', library]),
        ('VDA-client', common + ['-Dmain=KPVDAMain', '-Wno-deprecated-declarations',
                                '-c', out / sources[2], '-o', out / 'vda.o']),
        ('VT-client', common + ['-c', out / sources[3], '-o', out / 'vt.o']),
        ('host', common + [out / sources[1], out / 'vda.o', out / 'vt.o', library, '-framework', 'Foundation',
                           '-framework', 'VideoDecodeAcceleration', '-framework', 'CoreVideo',
                           '-framework', 'VideoToolbox', '-framework', 'CoreMedia', '-framework', 'Metal',
                           '-Wl,-export_dynamic', '-o', out / 'application']),
    ]
    records = []
    for label, argv in commands:
        argv = list(map(str, argv))
        result = subprocess.run(argv, capture_output=True, text=True, timeout=60)
        (out / (label + '.stdout')).write_text(result.stdout)
        (out / (label + '.stderr')).write_text(result.stderr)
        records.append({'label': label, 'argv': argv, 'exit_code': result.returncode})
        (out / 'commands.json').write_text(json.dumps(records, indent=2) + '\n')
        assert result.returncode == 0, result.stderr
    (out / 'assets/observer-config.json').write_text(json.dumps({
        'observer_library_SHA256': sha(library), 'source_fixture': fixture.name,
        'unknown_vendor_API_called_directly': False, 'system_changes': False}, indent=2) + '\n')
    inputs = {'source_hashes': {n: sha(out / n) for n in sources + ['builder.py']},
              'assets_SHA256': {str(p.relative_to(out / 'assets')): sha(p)
                                for p in (out / 'assets').rglob('*') if p.is_file()},
              'runtime_SHA256': {p.name: sha(p) for p in (out / 'runtime').iterdir()},
              'executable_SHA256': sha(out / 'application'), 'observer_library_SHA256': sha(library),
              'native_VDA_object_SHA256': sha(out / 'vda.o'),
              'fixture_files': len(files), 'GPU_execution': False,
              'scope': 'Own-process public VDA and ABI-neutral lookup tails; no original instruction/argument changes'}
    (out / 'inputs.json').write_text(json.dumps(inputs, indent=2) + '\n')
    print(json.dumps({'status': 'BUILT', 'GPU_work': 0, 'observer_library_SHA256': sha(library)}))


if __name__ == '__main__':
    main()
