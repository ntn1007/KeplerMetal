#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify construction-only native compiler evidence, never GPU execution."""
from pathlib import Path
from public_large_scratch import read
from verify_air_reset_dataflow import verify as verify_inspection

PROFILE = 'typed-quad-render-air28-experiment-v1'


def verify(path):
    path = Path(path)
    inputs = read(path / 'inputs.json')
    assert inputs['profile'] == PROFILE and inputs['inspection_only_host'] is True and inputs['mode'] == 'inspect'
    result = verify_inspection(path)
    assert result['mode'] == 'inspect'
    return result
