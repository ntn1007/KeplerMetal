#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build or run one exact-profile, own-process AppleVA availability experiment.

This never installs software, changes system policy, or invokes decoder factories.
Private entry invocation is restricted by the native host's fixed resident pins.
"""
from pathlib import Path
import argparse
import hashlib
import json
import plistlib
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ['video_policy_query.mm', 'video_policy_observer.mm', 'video_image_catalog.mm']
LIBRARY = 'libVideoPolicyObserver.dylib'
POLICY = Path('/System/Library/Extensions/AppleVADriver.bundle/Contents/Info.plist')
POLICY_SHA = 'e5cff89218a12c5a55b35832f13fa9552c1990d8f8100a68a7e9f0848fbfb0dc'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def build(out):
    if sha(POLICY) != POLICY_SHA:
        raise ValueError('System policy differs from the inspected profile; refusing build')
    out.mkdir(exist_ok=False)
    (out / 'assets').mkdir()
    (out / 'runtime').mkdir()
    for name in SOURCES:
        shutil.copyfile(ROOT / 'tools' / name, out / name)
    shutil.copyfile(Path(__file__), out / 'builder.py')
    for name, path in {'run_sdk_host.py': ROOT / 'sdk-combined/runtime/run_sdk_host.py',
                       'lab_gpu_reservation.py': ROOT / 'tools/lab_gpu_reservation.py'}.items():
        shutil.copyfile(path, out / 'runtime' / name)
    # These minimal policies are original test data, not copies of Apple's table.
    for mode, model in [('wrong-model', 'KeplerMetal-Control-NoMatch'), ('model-entry', 'iMac11,1')]:
        policy = {'System Support': {model: {'boostIG': False, 'disallowBGRA': False}}}
        (out / 'assets' / (mode + '.plist')).write_bytes(plistlib.dumps(policy, fmt=plistlib.FMT_XML))
    library = out / LIBRARY
    common = ['clang++', '-arch', 'x86_64', '-O2', '-std=c++17', '-fno-objc-arc',
              '-Wno-deprecated-declarations']
    commands = [
        ('observer', common + ['-dynamiclib', out / 'video_policy_observer.mm', '-framework', 'Foundation',
            '-install_name', library, '-o', library]),
        ('sign-observer', ['codesign', '--force', '--sign', '-', library]),
        ('host', common + [out / 'video_policy_query.mm', out / 'video_image_catalog.mm', library,
            '-framework', 'Foundation', '-framework', 'VideoToolbox', '-o', out / 'application']),
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
    overlays = {p.name: sha(p) for p in (out / 'assets').iterdir()}
    write(out / 'assets/config.json', {'policy_library_SHA256': sha(library), 'overlay_SHA256': overlays})
    write(out / 'inputs.json', {
        'source_hashes': {n: sha(out / n) for n in SOURCES + ['builder.py']},
        'assets_SHA256': {p.name: sha(p) for p in (out / 'assets').iterdir()},
        'runtime_SHA256': {p.name: sha(p) for p in (out / 'runtime').iterdir()},
        'executable_SHA256': sha(out / 'application'), 'policy_library_SHA256': sha(library),
        'policy_SHA256': POLICY_SHA, 'GPU_execution': False,
        'scope': 'Pinned int32_t(void) availability only; no decoder factory or system changes'})
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
        raise RuntimeError('Probe failed; retained terminal manifest and stderr are authoritative')
    result = json.loads((out / 'execution/execution.stdout').read_text())
    write(out / 'results.json', result)
    shutil.copyfile(out / 'outputs/images.json', out / 'images.json')
    if sha(POLICY) != POLICY_SHA or sha(build_root / LIBRARY) != inputs['policy_library_SHA256']:
        raise ValueError('A pinned dependency changed during the observation')
    print(json.dumps({'status': 'PROCESS_COMPLETED', 'mode': mode, 'pid': manifest['pid'],
        'exit_code': manifest['exit_code'], 'query_status': result['query_status'],
        'policy_events': len(result['policy']['events']), 'hardware_video_execution_proved': False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'run'])
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--build', type=Path)
    parser.add_argument('--mode', choices=['inspect', 'native', 'wrong-model', 'model-entry'])
    args = parser.parse_args()
    out = args.out.resolve()
    out.relative_to(ROOT / 'results')
    if args.action == 'build':
        build(out)
    else:
        if not args.build or not args.mode:
            parser.error('run requires --build and --mode')
        run(args.build.resolve(), out, args.mode)


if __name__ == '__main__':
    main()
