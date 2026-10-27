#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the ordinary two-word control, without claiming GPU execution."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def verify(path):
    path = Path(path)
    code = ('import sys,json;sys.path.insert(0,sys.argv[1]);'
            'from verify_native_render_pipeline_probe import verify;print(json.dumps(verify(sys.argv[2])))')
    p = subprocess.run([sys.executable, '-I', '-c', code, str(path/'oracles'), str(path)],
                       capture_output=True, text=True, check=True)
    assert json.loads(p.stdout)['status'] == 'PASS_NATIVE_OBSERVATION'
    inputs = json.loads((path/'inputs.json').read_text())
    data = json.loads((path/'results.json').read_text())
    assert inputs['probe_source'] == 'air_render_pipeline_plain_root'
    assert data['typed_function_encoder']['reflection_size'] == 16
    assert data['typed_function_encoder']['reflection_alignment'] == 8
    assert data['typed_function_encoder']['encoded_length'] == 16
    assert data['typed_compute_pipeline']['created'] is True
    assert data['GPU_command_buffers'] == data['GPU_dispatches'] == 0
    return {'status': 'PASS_PLAIN_ROOT_CONSTRUCTION', 'dispatches': 0,
            'ordinary_root_bytes': 16, 'compute_pipeline_created': True,
            'gpu_execution_proved': False,
            'signed_manifest_sha256': hashlib.sha256((path/'execution/manifest.json').read_bytes()).hexdigest()}


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('observation')
    args = p.parse_args()
    print(json.dumps(verify(args.observation), indent=2))
