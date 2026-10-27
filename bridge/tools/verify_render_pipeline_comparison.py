#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare construction-only observations. No GPU work is proved here."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(gtx, reference_input, reference_output):
    gtx, reference_input, reference_output = map(Path, (gtx, reference_input, reference_output))
    code = ('import sys,json;sys.path.insert(0,sys.argv[1]);'
            'from verify_native_render_pipeline_probe import verify;print(json.dumps(verify(sys.argv[2])))')
    result = subprocess.run([sys.executable, '-I', '-c', code, str(gtx/'oracles'), str(gtx)],
                            capture_output=True, text=True, check=True)
    assert json.loads(result.stdout)['status'] == 'PASS_NATIVE_OBSERVATION'
    data = json.loads((gtx/'results.json').read_text())
    output = reference_output.read_text()
    split = output.index('{')
    lines = output[:split].splitlines()
    expected_files = {'air_render_pipeline_probe.metal', 'render_state_carrier.metal',
                      'native_render_pipeline_probe.mm'}
    seen = set()
    for line in lines:
        hexdigest, name = line.split(None, 1)
        name = name.strip()
        assert name in expected_files and name not in seen and hexdigest == digest(reference_input/name)
        seen.add(name)
    assert seen == expected_files
    for name in ('air_render_pipeline_probe.metal', 'render_state_carrier.metal'):
        assert digest(reference_input/name) == digest(gtx/'src'/name)
    source = (gtx/'src/native_render_pipeline_probe.mm').read_text()
    source = source.replace('#import "KeplerGPUIdentity.h"', '').replace(
        'NSDictionary*identity=KPKepler880MIdentity(d);if(!identity)return 2;',
        'NSDictionary*identity=@{@"reference_device":d.name?:@""};if(!d)return 2;')
    assert source == (reference_input/'native_render_pipeline_probe.mm').read_text()
    reference = json.loads(output[split:])
    assert reference['device'] == 'Apple M1 Max'
    for item in (data, reference):
        assert item['GPU_dispatches'] == item['GPU_command_buffers'] == 0
        assert item['interposition'] is False
        assert [x['support_icb_requested'] for x in item['encoded_pipelines']] == [False, True]
    assert [x['length'] for x in data['encoded_pipelines']] == [0, 0]
    assert [x['length'] for x in reference['encoded_pipelines']] == [8, 8]
    assert all(x['guards_intact'] for x in reference['encoded_pipelines'])
    assert data['typed_function_encoder']['encoded_length'] == 0
    assert reference['typed_function_encoder']['encoded_length'] == 16
    assert data['typed_compute_pipeline']['created'] is False
    assert 'Unsupported indirect argument kind "air.render_pipeline_state"' in data['typed_compute_pipeline']['error']
    assert reference['typed_compute_pipeline']['created'] is True
    return {'status': 'PASS_CONSTRUCTION_COMPARISON', 'dispatches': 0,
            'gtx_signed_manifest_sha256': digest(gtx/'execution/manifest.json'),
            'reference_output_sha256': digest(reference_output),
            'shader_sha256': digest(reference_input/'air_render_pipeline_probe.metal'),
            'gtx_encoder_bytes': 0, 'm1_encoder_bytes': 16,
            'gtx_compute_pipeline_created': False, 'm1_compute_pipeline_created': True,
            'reference_attestation': 'SSH output; no signed host receipt or GPU dispatch'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--gtx', required=True)
    parser.add_argument('--reference-input', required=True)
    parser.add_argument('--reference-output', required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.gtx, args.reference_input, args.reference_output), indent=2))
