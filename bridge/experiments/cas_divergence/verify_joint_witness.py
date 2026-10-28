#!/usr/bin/env python3
"""Compare joint branch/target markers against an independently verified baseline."""
import hashlib
import struct
from verify_branch_witness import verify_baseline

def compare(baseline, breport, trace, treport):
    rows = verify_baseline(baseline, breport)
    keys = ('status', 'device', 'registry_id', 'GPU_dispatch', 'command_status', 'threads', 'groups', 'variant', 'seed', 'pattern')
    if treport['mode'] != 'trace' or any(treport[k] != breport[k] for k in keys):
        raise ValueError('trace report differs')
    if len(trace) != 1712 or trace[:64] != b'\xa5' * 64 or trace[-64:] != b'\xa5' * 64:
        raise ValueError('trace guard differs')
    allowed = {0: {2}, 2: {0x98, 0x99}, 3: {0xb8, 0xb9}, 4: {0x30, 0x31}}
    histogram = {}
    for i, base in enumerate(rows):
        row = struct.unpack_from('<4I', trace, 64 + i * 16)
        if (row[0], row[2], row[3]) != (base[0], base[2], base[3]):
            raise ValueError('trace changed non-witness output')
        marker = row[1]
        if marker not in allowed[breport['pattern']]:
            raise ValueError('unexpected combined marker')
        histogram[str(marker)] = histogram.get(str(marker), 0) + 1
    return {'status': 'PASS', 'pattern': breport['pattern'], 'rows': len(rows), 'markers': histogram,
            'baseline_sha256': hashlib.sha256(baseline).hexdigest(), 'trace_sha256': hashlib.sha256(trace).hexdigest(),
            'direct_origin_proved': False, 'resident_instructions_read_back': False, 'all_paths_qualified': False}
