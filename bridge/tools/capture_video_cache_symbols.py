#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Capture bounded named cache functions for private, offline inspection only.

This establishes binary identities and boundaries, not private function ABIs.
It never loads a framework, calls a vendor function or modifies the cache.
"""
from pathlib import Path
import argparse
import bisect
import hashlib
import json
import shutil
import struct
import sys

from inspect_video_cache import Cache, inspect, image_map, linkedit_read, cstring, require, sha

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--expected-uuid', required=True)
    parser.add_argument('--symbol', action='append', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.relative_to(ROOT / 'results')
    require(1 <= len(args.symbol) <= 8 and len(set(args.symbol)) == len(args.symbol), 'one to eight unique names')
    cache = Cache(args.cache.resolve())
    mapped = image_map(args.cache.with_name(args.cache.name + '.map'), args.image)
    image, starts = inspect(cache, mapped[0]['start'], args.image)
    require(image['UUID'] == args.expected_uuid.lower().replace('-', ''), 'expected image UUID')
    table = image['symbol_table']
    raw = linkedit_read(cache, image, table['file_offset'], table['count']*16)
    symbols = {}
    for i in range(table['count']):
        offset, kind, section, description, address = struct.unpack_from('<IBBHQ', raw, i*16)
        if kind & 14 != 14 or not offset or offset >= table['strings_size']:
            continue
        data = linkedit_read(cache, image, table['strings_offset']+offset, min(4096, table['strings_size']-offset))
        name = cstring(data, 0, len(data))
        if name in args.symbol:
            require(name not in symbols, 'ambiguous named symbol')
            symbols[name] = address
    require(set(symbols) == set(args.symbol), 'all requested named functions must exist')
    out.mkdir(exist_ok=False)
    for source in [Path(__file__), Path(__file__).with_name('inspect_video_cache.py')]:
        shutil.copyfile(source, out / source.name)
    records = []
    for index, name in enumerate(args.symbol):
        address = symbols[name]
        at = bisect.bisect_left(starts, address)
        require(at+1 < len(starts) and starts[at] == address, 'named function must equal a function-start entry')
        begin, end = starts[at:at+2]
        require(0 < end-begin <= 65536, 'bounded named function')
        data = cache.read(begin, end-begin)
        folder = out / ('function-%02d' % index)
        folder.mkdir()
        (folder / 'function-region.private.bin').write_bytes(data)
        region = {'name': name, 'target_VM': address, 'start_VM': begin, 'end_VM': end,
                  'bytes': len(data), 'SHA256': hashlib.sha256(data).hexdigest(), 'boundary_source': 'LC_FUNCTION_STARTS',
                  'function_ABI_established': False}
        m = {'status': 'PASS', 'image': image, 'image_base_VM': mapped[0]['start'], 'region': region,
             'region_captured_privately': True, 'expected_UUID_matched': True, 'resident_code_identity_proved': False,
             'source_function_invoked': False, 'system_modified': False}
        (folder / 'metadata.json').write_text(json.dumps(m, indent=2) + '\n')
        records.append({'folder': folder.name, 'symbol': name, 'region_SHA256': region['SHA256'],
                        'metadata_SHA256': sha(folder / 'metadata.json'), 'bytes': len(data)})
    parts = []
    for i in sorted(cache.used):
        part = dict(cache.parts[i])
        part['SHA256'] = sha(part['path'])
        parts.append(part)
    result = {'status': 'PASS', 'argv': sys.argv, 'image_UUID': image['UUID'], 'records': records,
              'cache_parts_read': parts, 'source_hashes': {p.name: sha(out / p.name)
                  for p in [Path(__file__), Path(__file__).with_name('inspect_video_cache.py')]},
              'function_ABIs_established': False, 'vendor_program_executed': False, 'system_modified': False}
    (out / 'capture.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': 'PASS', 'image_UUID': image['UUID'], 'functions': records, 'executed': False}))


if __name__ == '__main__':
    main()
