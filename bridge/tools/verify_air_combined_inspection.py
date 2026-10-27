#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Construction-only receipt verifier; no GPU execution is implied."""
from pathlib import Path
from public_large_scratch import read
from verify_air_reset_dataflow import verify as verify_inspection
PROFILE='typed-combined-index-vertex-air28-v1'

def verify(path):
    path=Path(path);m=read(path/'inputs.json')
    assert m['profile']==PROFILE and m['inspection_only_host'] is True and m['mode']=='inspect'
    d=verify_inspection(path);assert d['mode']=='inspect';return d
