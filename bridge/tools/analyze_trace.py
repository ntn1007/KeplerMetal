#!/usr/bin/env python3
"""Interpret the shape of our observed descriptor; leave semantics unknown."""
from pathlib import Path
import json
import struct

root = Path(__file__).resolve().parents[1]
connections = {}
phase = None
descriptors = []
for line in (root / 'results/iokit-trace.jsonl').read_text().splitlines():
    event = json.loads(line)
    if event['event'] == 'mark':
        phase = event['phase']
    if event['event'] == 'open' and event['status'] == 0:
        connections[event['connection']] = event
    if event['event'] != 'descriptor_observed':
        continue
    connection = connections.get(event['connection'], {})
    if connection.get('service') != 'nvAccelerator' or connection.get('type') != 8:
        continue
    payload = bytes.fromhex(event['hex'])
    field0, count, field8, field12, field16, field24 = struct.unpack('<IIIIQQ', payload)
    descriptors.append({
        'sequence': event['sequence'], 'phase': phase, 'selector': event['selector'],
        'client_type': 8, 'bytes': len(payload),
        'u32_at_0': field0, 'candidate_count_at_4': count,
        'u32_at_8': field8, 'u32_at_12': field12,
        'opaque_u64_at_16': hex(field16), 'opaque_u64_at_24': hex(field24),
        'matches_historical_8_plus_24_count_layout': len(payload) == 8 + 24 * count,
        'resource_and_fence_semantics_confirmed': False,
    })
result = {'descriptors': descriptors,
          'provenance': 'read-only tracing of our own successful Metal probe',
          'native_nak_program_submitted': False,
          'blocking_contracts': ['resource creation and GPU virtual addresses',
                                'command-stream/token encoding',
                                'constant buffers and Kepler QMD ownership',
                                'fences, barriers, completion and resource lifetimes']}
(root / 'results/descriptor-analysis.json').write_text(json.dumps(result, indent=2) + '\n')
print(json.dumps(result, indent=2))
