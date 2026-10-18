#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build/run bounded public anonymous-XPC controls under the common lab lease."""
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


def load(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    path.write_text(json.dumps(data, indent=2) + '\n')


def build(args):
    out, parent = args.out.resolve(), args.runtime_build.resolve()
    data = load(parent / 'inputs.json')
    for name, digest in data['runtime_SHA256'].items():
        if sha(parent / 'runtime' / name) != digest:
            raise ValueError('Qualified runner changed')
    out.mkdir(exist_ok=False)
    shutil.copytree(parent / 'runtime', out / 'runtime')
    shutil.copyfile(ROOT / 'tools/video_local_xpc_probe.mm', out / 'probe.mm')
    shutil.copyfile(__file__, out / 'builder.py')
    argv = ['clang++', '-arch', 'x86_64', '-O2', '-std=c++17', '-fblocks', '-fno-objc-arc',
            str(out / 'probe.mm'), '-framework', 'Foundation', '-o', str(out / 'application')]
    start = time.monotonic()
    q = subprocess.run(argv, capture_output=True, timeout=60)
    (out / 'build.stdout').write_bytes(q.stdout)
    (out / 'build.stderr').write_bytes(q.stderr)
    write(out / 'commands.json', [{'argv': argv, 'exit_code': q.returncode,
                                 'diagnostic_build_seconds': time.monotonic() - start}])
    if q.returncode:
        raise RuntimeError('Build failed; retained stderr')
    write(out / 'inputs.json', {'source_hashes': {n: sha(out / n) for n in ['probe.mm', 'builder.py']},
        'runtime_SHA256': data['runtime_SHA256'], 'assets_SHA256': {}, 'executable_SHA256': sha(out / 'application'),
        'qualified_runner_build': str(parent), 'qualified_runner_inputs_SHA256': sha(parent / 'inputs.json'),
        'GPU_execution': False, 'private_video_handler_called': False, 'named_service_modified': False})
    print(json.dumps({'status': 'BUILT', 'GPU_work': 0, 'named_service_modified': False}))


def run(args):
    build, out = args.build.resolve(), args.out.resolve()
    data = load(build / 'inputs.json')
    for name, digest in data['source_hashes'].items():
        if sha(build / name) != digest:
            raise ValueError('Frozen source changed')
    for name, digest in data['runtime_SHA256'].items():
        if sha(build / 'runtime' / name) != digest:
            raise ValueError('Frozen runner changed')
    if sha(build / 'application') != data['executable_SHA256']:
        raise ValueError('Frozen executable changed')
    if not 0 <= args.seed <= 0xffffffff:
        raise ValueError('uint32 seed required')
    out.mkdir(exist_ok=False)
    (out / 'outputs').mkdir()
    (out / 'assets').mkdir()
    shutil.copyfile(build / 'application', out / 'application')
    (out / 'application').chmod(0o755)
    for name in data['source_hashes']:
        shutil.copyfile(build / name, out / name)
    shutil.copyfile(__file__, out / 'runner.py')
    write(out / 'inputs.json', {**data, 'mode': args.mode, 'seed': args.seed})
    sys.path.insert(0, str(build / 'runtime'))
    from run_sdk_host import run_host
    manifest = run_host(out / 'application', out / 'execution',
        [args.mode, str(out / 'outputs'), str(args.seed)], args.reservation_root.resolve())
    result = load(out / 'execution/execution.stdout')
    write(out / 'results.json', result)
    print(json.dumps({'status': result['status'], 'mode': args.mode, 'PID': manifest['pid'],
        'requests': result['requests'], 'context_destroyed': result['context_destroyed'],
        'same_process': result['same_process'], 'GPU_work': result['GPU_work']}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['build', 'run'])
    parser.add_argument('--runtime-build', type=Path)
    parser.add_argument('--build', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--mode', choices=['sync', 'async', 'cancel'])
    parser.add_argument('--seed', type=lambda value: int(value, 0), default=0x13579)
    parser.add_argument('--reservation-root', type=Path, default=ROOT)
    args = parser.parse_args()
    args.out.resolve().relative_to(ROOT / 'results')
    if args.action == 'build':
        if not args.runtime_build:
            parser.error('build requires --runtime-build')
        build(args)
    else:
        if not args.build or not args.mode:
            parser.error('run requires --build and --mode')
        run(args)


if __name__ == '__main__':
    main()
