#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Execute one frozen image-catalogue probe under the original shared lab lease."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--mode', choices=['catalog', 'selftest', 'vt-cpu', 'vt-observe', 'observe'], required=True)
    args = parser.parse_args()
    build, out = args.build.resolve(), args.out.resolve()
    out.relative_to(ROOT / 'results')
    inputs = json.loads((build / 'inputs.json').read_text())
    for folder, key in [('', 'source_hashes'), ('assets', 'assets_SHA256'), ('runtime', 'runtime_SHA256')]:
        for name, digest in inputs[key].items():
            if sha(build / folder / name) != digest:
                raise ValueError('Changed frozen input: ' + name)
    for name, key in [('application', 'executable_SHA256'), ('libVideoVAObserver.dylib', 'observer_library_SHA256'),
                      ('libVideoImageFixture.dylib', 'calibration_library_SHA256')]:
        if sha(build / name) != inputs[key]:
            raise ValueError('Changed frozen native artefact: ' + name)
    out.mkdir(exist_ok=False)
    (out / 'outputs').mkdir()
    shutil.copytree(build / 'assets', out / 'assets')
    for name in [*inputs['source_hashes'], 'application', 'inputs.json']:
        shutil.copyfile(build / name, out / name)
    (out / 'application').chmod(0o755)
    shutil.copyfile(Path(__file__), out / 'runner.py')
    sys.path.insert(0, str(build / 'runtime'))
    from run_sdk_host import run_host
    m = run_host(out / 'application', out / 'execution', [str(out / 'assets'), str(out / 'outputs'), args.mode], ROOT)
    results = json.loads((out / 'execution/execution.stdout').read_text())
    images = json.loads((out / 'outputs/images.json').read_text())
    (out / 'results.json').write_text(json.dumps(results, indent=2) + '\n')
    (out / 'images.json').write_text(json.dumps(images, indent=2) + '\n')
    for name in ['libVideoVAObserver.dylib', 'libVideoImageFixture.dylib']:
        key = 'observer_library_SHA256' if name == 'libVideoVAObserver.dylib' else 'calibration_library_SHA256'
        if sha(build / name) != inputs[key]:
            raise ValueError('Native dependency changed during observation')
    print(json.dumps({'status': 'PROCESS_COMPLETED', 'pid': m['pid'], 'mode': args.mode,
                      'exit_code': m['exit_code'], 'images_seen': images['final']['added'],
                      'hardware_video_execution_proved': False}))


if __name__ == '__main__':
    main()
