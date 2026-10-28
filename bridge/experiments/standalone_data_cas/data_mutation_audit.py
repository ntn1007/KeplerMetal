#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prove the data-load oracle rejects a missing data-path witness offline."""
import argparse, importlib.util, json, shutil, tempfile
from pathlib import Path

here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('data_cas_verify', here / 'verify.py')
v = importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--optin-data', type=Path, required=True)
    source = parser.parse_args().optin_data.resolve()
    if v.verify(source)['mode'] != 'optin-b':
        raise ValueError('Expected data-path run')
    with tempfile.TemporaryDirectory(prefix='kepler-data-witness-') as tmp:
        dest = Path(tmp).resolve() / 'run'
        shutil.copytree(source, dest)
        manifest_path = dest / 'execution/manifest.json'
        manifest = json.loads(manifest_path.read_text())
        manifest['arguments'] = [str(dest / 'assets/cas_client.metallib'), str(dest / 'outputs'), 'run-data']
        manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
        v.verify(dest)
        trace = dest / 'execution/execution.stderr'
        text = trace.read_text()
        if text.count('KM_CAS data library matched') != 1:
            raise ValueError('Expected one data witness')
        trace.write_text(text.replace('KM_CAS data library matched', 'KM_CAS data witness missing', 1))
        try:
            v.verify(dest)
        except ValueError:
            pass
        else:
            raise ValueError('Missing data witness was accepted')
    print(json.dumps({'status':'PASS','unchanged':'PASS','missing_data_witness':'EXPECTED_REFUSAL','GPU_dispatch':False}, sort_keys=True))

if __name__ == '__main__':
    main()
