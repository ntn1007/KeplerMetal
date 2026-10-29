#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check the pinned offline AppleGVA list-reset and cached-byte paths."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

START = 148746
REGION = 'f8a1efea62ed7f03028666fe86c35de8f06941324ac8d1ae8815ec93f0eb8a19'
MAPPING = '2d9c4ed04bcdbdd4049bb7ed88f0a545d3f42b1b478ab320e43fc8feb6a39ffd'
WINDOWS = {
    'reset': (0x537, 0x55e, '85c594011332622077d67431498df11d75c561545c56528087ddb10a997f239a'),
    'lookup': (0x645, 0x692, 'b41ffc38c5e78526b2c7b83c9de39ee61f789b6109c5bb1b8893a48d2437c608'),
    'allocation': (0x692, 0x6e2, '6c689ab3491517c03c1603209adbef41e1632d100482ac4057e5af693fa9ee0c'),
    'conversion': (0x80d, 0x840, '9906572baa19d659c60d32846526992c7bf2645c862d5586778d59cd585967e0'),
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def need(value, message):
    if not value:
        raise ValueError(message)


def relative_target(data, offset, size, displacement_offset):
    formats = {1: '<b', 4: '<i'}
    displacement = struct.unpack_from(formats[size], data, offset + displacement_offset)[0]
    return offset + displacement_offset + size + displacement


def inspect(data, mapping):
    need(len(data) == 2669 and digest(data) == REGION, 'region pin mismatch')
    need(digest(mapping) == MAPPING, 'mapping pin mismatch')
    rows = json.loads(mapping)
    need(rows['status'] == 'STATIC_ONLY' and not rows['runtime_target_proved'], 'mapping scope mismatch')
    calls = {x['caller_offset']: x for x in rows['rows']}
    for offset, symbol in ((150807, '_IORegistryEntryCreateCFProperty'),
                           (150845, '_CFStringGetCString'), (150853, '_CFRelease')):
        need(symbol in calls[offset]['exact_defined_symbols'], 'call mapping mismatch')
    for name, (begin, end, expected) in WINDOWS.items():
        need(digest(data[begin:end]) == expected, name + ' instruction window mismatch')
    branches = [(0x541, 1, 1, 0x55e), (0x54d, 1, 1, 0x556),
                (0x55c, 1, 1, 0x546), (0x65c, 1, 1, 0x692),
                (0x669, 1, 1, 0x656), (0x676, 4, 2, 0x763),
                (0x680, 4, 2, 0x763), (0x68d, 4, 1, 0x8af),
                (0x815, 1, 1, 0x840)]
    for at, size, pos, target in branches:
        need(relative_target(data, at, size, pos) == target, 'branch target mismatch')
    return {
        'status': 'PASS_STATIC_BOUNDED', 'region_sha256': REGION, 'mapping_sha256': MAPPING,
        'image_function_start_offset': START,
        'window_sha256': {name: row[2] for name, row in WINDOWS.items()},
        'reset_nonzero_identifier_offset': START + 0x54f,
        'matching_identifier_check_offset': START + 0x664,
        'matching_auxiliary_byte_check_offset': START + 0x671,
        'cached_first_byte_check_offset': START + 0x67c,
        'cached_reactivation_offset': START + 0x686,
        'property_call_offset': START + 0x80d,
        'flag_set_before_conversion_offset': START + 0x81a,
        'conversion_call_offset': START + 0x833,
        'conversion_destination_node_offset': 8,
        'cached_first_byte_node_offset': 8,
        'branch_targets_verified': len(branches),
        'runtime_reactivation_observed': False, 'node_lifetime_proved': False,
        'nvidia_value_identified': False, 'hardware_video_execution_proved': False,
        'system_modified': False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--region', required=True, type=Path)
    p.add_argument('--mapping', required=True, type=Path)
    p.add_argument('--out', required=True, type=Path)
    a = p.parse_args()
    need(a.out.parent.is_dir() and not a.out.exists(), 'fresh output required')
    result = inspect(a.region.read_bytes(), a.mapping.read_bytes())
    result['auditor_sha256'] = digest(Path(__file__).read_bytes())
    with a.out.open('x') as f:
        json.dump(result, f, indent=2, sort_keys=True)
        f.write('\n')
    print(json.dumps({'status': result['status'], 'branch_targets_verified': result['branch_targets_verified'],
                      'hardware_video_execution_proved': False}))


if __name__ == '__main__':
    main()
