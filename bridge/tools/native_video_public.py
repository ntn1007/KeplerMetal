#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build/run public H264/MPEG2 decode with the exact-profile, own-process observer."""
from pathlib import Path
import argparse
import hashlib
import json
import plistlib
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ['video_policy_public.mm', 'video_policy_profile.h', 'video_policy_observer.mm',
           'video_image_catalog.mm', 'video_va_vt_client.mm', 'video_engine_probe.mm']
LIBRARY = 'libVideoPolicyObserver.dylib'
POLICY = Path('/System/Library/Extensions/AppleVADriver.bundle/Contents/Info.plist')
POLICY_SHA = 'e5cff89218a12c5a55b35832f13fa9552c1990d8f8100a68a7e9f0848fbfb0dc'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def build(out, fixture, codec):
    if sha(POLICY) != POLICY_SHA:
        raise ValueError('System policy differs from inspected profile')
    files = list(fixture.iterdir())
    extension = 'avcc' if codec == 'H264' else 'm2v'
    if len(files) != 13 or not all(p.is_file() and not p.is_symlink() and re.fullmatch(
            r'fixture\.json|frame-\d{3}\.' + extension + r'|cpu-frame-\d{3}\.nv12', p.name) for p in files):
        raise ValueError('Expected six codec samples, six independent CPU references and fixture.json')
    out.mkdir(exist_ok=False)
    (out / 'assets/fixture').mkdir(parents=True)
    (out / 'runtime').mkdir()
    sources = SOURCES + (['video_mpeg2_vt_client.mm'] if codec == 'MPEG2Video' else [])
    for name in sources:
        shutil.copyfile(ROOT / 'tools' / name, out / name)
    shutil.copyfile(Path(__file__), out / 'builder.py')
    for p in files:
        shutil.copyfile(p, out / 'assets/fixture' / p.name)
    for name, path in {'run_sdk_host.py': ROOT / 'sdk-combined/runtime/run_sdk_host.py',
                       'lab_gpu_reservation.py': ROOT / 'tools/lab_gpu_reservation.py'}.items():
        shutil.copyfile(path, out / 'runtime' / name)
    for mode, model in [('wrong-model', 'KeplerMetal-Control-NoMatch'), ('model-entry', 'iMac11,1')]:
        (out / 'assets' / (mode + '.plist')).write_bytes(plistlib.dumps(
            {'System Support': {model: {'boostIG': False, 'disallowBGRA': False}}}, fmt=plistlib.FMT_XML))
    library = out / LIBRARY
    common = ['clang++', '-arch', 'x86_64', '-O2', '-std=c++17', '-fno-objc-arc',
              '-Wno-deprecated-declarations']
    commands = [
        ('observer', common + ['-dynamiclib', out / 'video_policy_observer.mm', '-framework', 'Foundation',
            '-install_name', library, '-o', library]),
        ('sign-observer', ['codesign', '--force', '--sign', '-', library]),
        ('VT-client', common + ['-c', out / ('video_va_vt_client.mm' if codec == 'H264' else 'video_mpeg2_vt_client.mm'), '-o', out / 'vt.o']),
        ('host', common + ([] if codec == 'H264' else ['-DKPVideoVTFixtureDecode=KPVideoMPEG2FixtureDecode'])
            + [out / 'video_policy_public.mm', out / 'video_image_catalog.mm', out / 'vt.o', library,
            '-framework', 'Foundation', '-framework', 'VideoToolbox', '-framework', 'CoreMedia',
            '-framework', 'CoreVideo', '-framework', 'Metal', '-o', out / 'application']),
    ]
    records = []
    for label, argv in commands:
        argv = list(map(str, argv))
        result = subprocess.run(argv, capture_output=True, timeout=60)
        (out / (label + '.stdout')).write_bytes(result.stdout)
        (out / (label + '.stderr')).write_bytes(result.stderr)
        records.append({'label': label, 'argv': argv, 'exit_code': result.returncode})
        write(out / 'commands.json', records)
        if result.returncode:
            raise RuntimeError(label + ': inspect retained stderr')
    overlays = {p.name: sha(p) for p in (out / 'assets').glob('*.plist')}
    write(out / 'assets/config.json', {'policy_library_SHA256': sha(library), 'overlay_SHA256': overlays, 'codec': codec})
    write(out / 'inputs.json', {'source_hashes': {n: sha(out / n) for n in sources + ['builder.py']},
        'assets_SHA256': {str(p.relative_to(out / 'assets')): sha(p) for p in (out / 'assets').rglob('*') if p.is_file()},
        'runtime_SHA256': {p.name: sha(p) for p in (out / 'runtime').iterdir()},
        'executable_SHA256': sha(out / 'application'), 'policy_library_SHA256': sha(library),
        'native_objects_SHA256': {'vt.o': sha(out / 'vt.o')}, 'policy_SHA256': POLICY_SHA,
        'GPU_execution': False, 'private_ABI_invocation': False})
    print(json.dumps({'status': 'BUILT', 'GPU_work': 0}))


def run(build_root, out, mode):
    inputs = json.loads((build_root / 'inputs.json').read_text())
    for folder, key in [('', 'source_hashes'), ('assets', 'assets_SHA256'), ('runtime', 'runtime_SHA256')]:
        for name, digest in inputs[key].items():
            if sha(build_root / folder / name) != digest:
                raise ValueError('Changed frozen input: ' + name)
    for name, key in [('application', 'executable_SHA256'), (LIBRARY, 'policy_library_SHA256')]:
        if sha(build_root / name) != inputs[key]:
            raise ValueError('Changed native artifact: ' + name)
    if sha(POLICY) != POLICY_SHA:
        raise ValueError('System policy changed; refusing execution')
    out.mkdir(exist_ok=False)
    (out / 'outputs').mkdir()
    shutil.copytree(build_root / 'assets', out / 'assets')
    for name in [*inputs['source_hashes'], 'application', 'inputs.json']:
        shutil.copyfile(build_root / name, out / name)
    (out / 'application').chmod(0o755)
    shutil.copyfile(Path(__file__), out / 'runner.py')
    sys.path.insert(0, str(build_root / 'runtime'))
    from run_sdk_host import run_host
    manifest = run_host(out / 'application', out / 'execution',
        [str(out / 'assets'), str(out / 'outputs'), mode], ROOT)
    if manifest['exit_code'] != 0:
        raise RuntimeError('Probe failed; retained manifest/stderr are authoritative')
    result = json.loads((out / 'execution/execution.stdout').read_text())
    write(out / 'results.json', result)
    shutil.copyfile(out / 'outputs/images.json', out / 'images.json')
    if sha(POLICY) != POLICY_SHA or sha(build_root / LIBRARY) != inputs['policy_library_SHA256']:
        raise ValueError('Pinned dependency changed during observation')
    decoded = result['public_decode']
    print(json.dumps({'status': 'PROCESS_COMPLETED', 'mode': mode, 'pid': manifest['pid'],
        'exit_code': manifest['exit_code'], 'policy_events': len(result['policy']['events']),
        'decode_create_status': decoded['decode']['create_status'] if decoded else None,
        'output_frames': decoded['output_frames'] if decoded else 0, 'hardware_video_execution_proved': False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'run'])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--build', type=Path)
    parser.add_argument('--fixture', type=Path)
    parser.add_argument('--mode', choices=['inspect', 'cpu', 'native', 'wrong-model', 'model-entry'])
    parser.add_argument('--codec', choices=['H264', 'MPEG2Video'], default='H264')
    args = parser.parse_args()
    out = args.out.resolve()
    out.relative_to(ROOT / 'results')
    if args.action == 'build':
        if not args.fixture:
            parser.error('build requires --fixture')
        build(out, args.fixture.resolve(), args.codec)
    else:
        if not args.build or not args.mode:
            parser.error('run requires --build and --mode')
        run(args.build.resolve(), out, args.mode)


if __name__ == '__main__':
    main()
