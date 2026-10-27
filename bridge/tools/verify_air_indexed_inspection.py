#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Construction-only indexed shader receipts; never implies GPU execution."""
from pathlib import Path
from public_large_scratch import read
from verify_air_reset_dataflow import verify as verify_inspection
PROFILE='typed-indexed-render-air28-v1'


def verify(path):
    path=Path(path);m=read(path/'inputs.json')
    assert m['profile']==PROFILE and m['inspection_only_host']is True and m['mode']=='inspect'
    proof=verify_inspection(path);assert proof['mode']=='inspect'
    return proof
