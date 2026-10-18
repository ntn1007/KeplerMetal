#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Map bounded x86_64 cache stubs through verified slide-v2 GOT members.

These are static cache targets, not observations of runtime resolution. Scan
each target image's nlist once in bounded pages; never read its whole shared
string table. No image is loaded, invoked, reconstructed or modified.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import struct

from inspect_video_cache import Cache, inspect, linkedit_read, require, cstring, sha


def catalogue(path):
    current, rows = None, []
    for line in path.read_text().splitlines():
        if line.startswith('/'):
            current = line
        elif current:
            m = re.fullmatch(r'\s+__TEXT\s+(0x[0-9A-Fa-f]+) -> (0x[0-9A-Fa-f]+)', line)
            if m:
                rows.append((int(m[1], 16), int(m[2], 16), current))
    require(rows, 'cache image catalogue absent')
    return rows


def exact_symbols(cache, image, targets):
    table = image['symbol_table']; found = {t: [] for t in targets}
    require(0 <= table['count'] <= 2000000, 'bounded symbol count')
    for first in range(0, table['count'], 4096):
        count = min(4096, table['count'] - first)
        page = linkedit_read(cache, image, table['file_offset'] + first * 16, count * 16)
        for i in range(count):
            nameoff, kind, _, _, value = struct.unpack_from('<IBBHQ', page, i * 16)
            if kind not in (14, 15) or value not in found:
                continue
            require(nameoff < table['strings_size'], 'defined symbol name extent')
            text = linkedit_read(cache, image, table['strings_offset'] + nameoff,
                                 min(4096, table['strings_size'] - nameoff))
            found[value].append(cstring(text, 0, len(text)))
    return found


def map_targets(cache_path, analysis_path, record_index):
    analysis = json.loads(analysis_path.read_text())
    require(analysis['status'] == 'STATIC_ONLY' and not analysis['vendor_program_executed'], 'static analysis input')
    require(0 <= record_index < len(analysis['records']), 'record index')
    record = analysis['records'][record_index]
    require(len(record['calls']) <= 4096, 'bounded call list')
    capture = Path(record['capture']); metadata = json.loads((capture / 'metadata.json').read_text())
    require(sha(capture / 'metadata.json') == record['metadata_SHA256']
            and sha(capture / 'function-region.private.bin') == record['region_SHA256'], 'capture identity')
    cache = Cache(cache_path); images = catalogue(cache_path.with_name(cache_path.name + '.map'))
    mapped, targets, inspected = {}, {}, {}
    stubs = {r['target_VM'] for r in record['calls'] if r['static_binding'] is not None}
    require(len(stubs) <= 256, 'bounded stub set')
    for stub in sorted(stubs):
        sections = [s for s in metadata['image']['sections'] if s['flags'] & 255 == 8
                    and s['VM_address'] <= stub < s['VM_address'] + s['size']]
        require(len(sections) == 1 and sections[0]['reserved2'] == 6
                and (stub-sections[0]['VM_address']) % 6 == 0, 'six-byte stub section')
        raw = cache.read(stub, 6); require(raw[:2] == b'\xff\x25', 'supported RIP-relative GOT stub')
        slot = stub + 6 + struct.unpack_from('<i', raw, 2)[0]
        target = cache.pointer_v2(slot)
        matches = [r for r in images if r[0] <= target < r[1]]
        require(len(matches) == 1, 'unique target text image')
        start, _, name = matches[0]
        if name not in inspected:
            inspected[name] = inspect(cache, start, name)[0]
        targets.setdefault(name, set()).add(target)
        mapped[stub] = dict(stub_VM=stub, verified_GOT_VM=slot, static_target_VM=target,
                            target_module=name, target_image_offset=target-start,
                            target_UUID=inspected[name]['UUID'], runtime_target_proved=False)
    names = {name: exact_symbols(cache, inspected[name], values) for name, values in targets.items()}
    rows = []
    for call in record['calls']:
        if call['target_VM'] in mapped:
            row = dict(mapped[call['target_VM']], caller_offset=call['site_image_offset'])
            row['exact_defined_symbols'] = names[row['target_module']][row['static_target_VM']]
            rows.append(row)
    return dict(status='STATIC_ONLY', analysis_SHA256=sha(analysis_path), record_index=record_index,
                source_region_SHA256=record['region_SHA256'], rows=rows, unique_stubs=len(stubs),
                source_SHA256=sha(Path(__file__)), vendor_program_executed=False,
                runtime_target_proved=False, system_modified=False,
                limits=['Verified static GOT rebase and exact defined symbol address; runtime binding may differ.',
                        'An empty symbol list remains unnamed; no closest-symbol substitution.'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache', type=Path, required=True)
    p.add_argument('--analysis', type=Path, required=True)
    p.add_argument('--record', type=int, default=0)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args(); require(not args.out.exists(), 'new output required')
    result = map_targets(args.cache.resolve(), args.analysis.resolve(), args.record)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'status': result['status'], 'calls': len(result['rows']),
                      'unique_stubs': result['unique_stubs'], 'report_SHA256': sha(args.out), 'executed': False}))


if __name__ == '__main__':
    main()
