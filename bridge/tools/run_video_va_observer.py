#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run one immutable video observation on the existing common laboratory lease."""
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
    parser.add_argument('--mode', choices=['selftest', 'plain', 'observe', 'vt-cpu', 'vt-plain', 'vt-observe'], required=True)
    args = parser.parse_args()
    build, out = args.build.resolve(), args.out.resolve()
    out.relative_to(ROOT / 'results')
    inputs = json.loads((build / 'inputs.json').read_text())
    assert sha(build / 'application') == inputs['executable_SHA256']
    assert sha(build / 'libVideoVAObserver.dylib') == inputs['observer_library_SHA256']
    for name, h in inputs['source_hashes'].items():
        assert sha(build / name) == h
    for name, h in inputs['assets_SHA256'].items():
        assert sha(build / 'assets' / name) == h
    for name, h in inputs['runtime_SHA256'].items():
        assert sha(build / 'runtime' / name) == h
    out.mkdir(exist_ok=False)
    (out / 'outputs').mkdir()
    shutil.copytree(build / 'assets', out / 'assets')
    for name in [*inputs['source_hashes'], 'application', 'inputs.json']:
        shutil.copyfile(build / name, out / name)
    (out / 'application').chmod(0o755)
    shutil.copyfile(Path(__file__), out / 'runner.py')
    sys.path.insert(0, str(build / 'runtime'))
    from run_sdk_host import run_host
    manifest = run_host(out / 'application', out / 'execution',
                        [str(out / 'assets'), str(out / 'outputs'), args.mode], ROOT)
    result = json.loads((out / 'execution/execution.stdout').read_text())
    observer = json.loads((out / 'outputs/observer.json').read_text())
    assert observer['observer_library_SHA256'] == sha(build / 'libVideoVAObserver.dylib') == inputs['observer_library_SHA256']
    (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    (out / 'observation.json').write_text(json.dumps(observer, indent=2) + '\n')
    print(json.dumps({'status': 'PROCESS_COMPLETED', 'mode': args.mode,
                      'pid': manifest['pid'], 'exit_code': manifest['exit_code'],
                      'create_status': result.get('create_status', result.get('decode', {}).get('create_status')),
                      'create_calls': observer['observer']['create_calls'],
                      'hardware_video_execution_proved': False}))


if __name__ == '__main__':
    main()
