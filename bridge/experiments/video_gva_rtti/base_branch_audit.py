#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Correlate a pinned constructor branch with a historical stack, offline."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

START = 117024
REGION = 'c4ef1c90c52e607a307e995c036890376ebf959ba9ade05725ff02c5cc1b7273'
OBJECT = '4bb4a9021217403a842874f832ccf13e32ac4db0950c78a1059cc2bc38f35403'
REA = 'ec626263a08fdb6a8e720c42c06416ff9072c34ee0d3a9251142426b23bec0d2'
STACK = 'd5ae8902628d7193c32fb159fcfced0f02070c00bf84fbdfc8e5cb34bd0c219d'
EVIDENCE = 'ev_f9bb0e6b5698dd40ae995e90c2aeeab583e9a5efba8a8cb6b11e57cc00292bfe'


def need(ok, why):
    if not ok:
        raise ValueError(why)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def check_branch(data):
    """Check bounded x86 branch and call bytes, returning image offsets."""
    need(len(data) == 176 and digest(data) == REGION, 'region differs')
    # cmp dword ptr [r14], -1; je <alternate>; argument loads; call rel32
    need(data[28:32] == bytes.fromhex('41833eff') and data[32] == 0x74,
         'compare or conditional branch differs')
    alternate = START + 34 + struct.unpack_from('<b', data, 33)[0]
    need(data[34:43] == bytes.fromhex('498b7e38410fb67640') and data[43] == 0xe8,
         'fall-through call differs')
    target = START + 48 + struct.unpack_from('<i', data, 44)[0]
    need(alternate == START + 50 and target == 148746, 'branch targets differ')
    return alternate, target


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ('capture', 'rea', 'stack-map', 'out'):
        p.add_argument('--' + key, type=Path, required=True)
    a = p.parse_args()
    need(a.out.parent.is_dir() and not a.out.exists(), 'fresh output required')
    metadata = json.loads((a.capture / 'metadata.json').read_text())
    region = (a.capture / 'function-region.private.bin').read_bytes()
    obj = (a.capture / 'analysis.private.o').read_bytes()
    need(metadata['image']['UUID'] == 'ca5414f369373c059ea2d82b35afd4f0' and
         metadata['region']['start_VM'] == 140711945218336 and
         metadata['region']['target_image_offset'] == START and
         metadata['region']['SHA256'] == REGION, 'metadata differs')
    alternate, target = check_branch(region)
    need(digest(obj) == OBJECT and len(obj) >= 64 and obj[:6] == b'\x7fELF\x02\x01',
         'analysis object differs')
    shoff = struct.unpack_from('<Q', obj, 40)[0]
    size, count = struct.unpack_from('<HH', obj, 58)
    need(size == 64 and 1 < count <= 64 and shoff + size * count <= len(obj), 'ELF table differs')
    sections = []
    for index in range(count):
        off = shoff + index * size
        kind = struct.unpack_from('<I', obj, off + 4)[0]
        address, fileoff, length = struct.unpack_from('<QQQ', obj, off + 16)
        if kind == 1 and length == len(region) and fileoff + length <= len(obj) and obj[fileoff:fileoff+length] == region:
            sections.append(address)
    need(sections == [metadata['region']['start_VM']], 'analysis object source section differs')
    rea, stack = a.rea.read_bytes(), a.stack_map.read_bytes()
    need(digest(rea) == REA and digest(stack) == STACK, 'evidence digest differs')
    records = [x for x in json.loads(rea)['records'] if x['evidence_id'] == EVIDENCE]
    need(len(records) == 1 and records[0]['operation'] == 'analyze_function' and
         records[0]['provider']['id'] == 'ghidra' and
         records[0]['subject']['digest']['sha256'] == OBJECT and
         records[0]['normalized_result']['procedure']['address'] == '0x7ffa0d92a920', 'REA identity differs')
    mapped = json.loads(stack)
    rows = [x for x in mapped['rows'] if x['return_offset'] == START + 48]
    need(mapped['status'] == 'STATIC_AND_RECORDED_STACK' and
         mapped['image_UUID'] == metadata['image']['UUID'] and
         mapped['live_code_identity_proved_for_every_frame'] is False and
         len(rows) == 1 and rows[0]['cache_region_SHA256'] == REGION and
         rows[0]['cache_function_start'] == START and
         rows[0]['static_direct_call_target'] == target, 'stack evidence differs')
    result = {'status': 'PASS_BOUNDED_STATIC_STACK_CORRELATION',
              'historical_stack_return_offset': START + 48, 'static_direct_call_target': target,
              'static_alternate_branch_offset': alternate,
              'inference_if_pinned_entry_flow_applies': 'compared word was not 0xffffffff',
              'live_comparison_or_value_observed': False, 'live_code_identity_for_all_frames_proved': False,
              'constructor_return_proved': False, 'video_engine_execution_proved': False,
              'historical_stack_and_selector_observation_are_separate_runs': True,
              'counterfactual_property_and_policy_used': True, 'region_sha256': REGION,
              'analysis_object_sha256': OBJECT, 'rea_evidence_id': EVIDENCE,
              'rea_bundle_sha256': REA, 'stack_map_sha256': STACK,
              'auditor_sha256': digest(Path(__file__).read_bytes()),
              'GPU_or_vendor_execution_during_audit': False, 'system_modified': False}
    with a.out.open('x') as f:
        json.dump(result, f, indent=2, sort_keys=True)
        f.write('\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
