#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck concurrent default-device calls and the standalone render oracle."""
from pathlib import Path
import json
import importlib.util
import sys

spec = importlib.util.spec_from_file_location('standalone_oracle', Path(__file__).with_name('verify.py'))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
verify = module.verify


def main(path):
    path = Path(path).resolve()
    row = verify(path)
    if row['mode'] != 'wrong-client':
        app = json.loads((path/'execution/execution.stdout').read_text())
        assert app['concurrent_device_calls'] == 8
        assert app['device_calls'] == 9 and app['identical_device_objects']
    trace = (path/'execution/execution.stderr').read_text()
    if row['mode'] in ('auto', 'wrong-library'):
        assert trace.count('KM_BOOT enter\n') == 9
        assert trace.count('KM_BOOT enabled\n') == 1
        assert trace.count('KM_BOOT device reused\n') == 8
    if row['mode'] == 'wrong-client':
        assert trace.count('KM_BOOT identity refused\n') == 1
        assert trace.count('KM_BOOT enter\n') == 8
        assert 'KM_BOOT enabled' not in trace
    row.update(concurrent_device_calls=8, total_device_calls=8 if row['mode']=='wrong-client' else 9,
               same_device_object_verified=(row['mode']!='wrong-client'))
    print(json.dumps(row, sort_keys=True))

if __name__ == '__main__': main(sys.argv[1])
