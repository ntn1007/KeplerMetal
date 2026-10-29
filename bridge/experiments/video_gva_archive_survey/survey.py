#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Stream an odc archive for one codec-property literal; never extract or execute.

The scan covers regular members and three literal encodings. It does not
interpret compressed payloads or prove that a runtime property is absent.
"""
import argparse
import hashlib
import json
import plistlib
import stat
from pathlib import Path

HIGH_SIZE = 5801167872
HIGH_SHA = 'b48e6eaaacb86400dfc9e84ed85a8df666baa24af7ca3a632b73607a1d2f4cc6'
KEY = 'IOGVACodec'
PATTERNS = {'ascii': KEY.encode(), 'utf16le': KEY.encode('utf-16le'), 'utf16be': KEY.encode('utf-16be')}
PLIST_LIMIT = 16 * 1024 * 1024


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def plist_values(item):
    values = []
    if isinstance(item, dict):
        for key, value in item.items():
            if key == KEY:
                values.append({'type': type(value).__name__, 'string': value if isinstance(value, str) and len(value) <= 128 else None})
            values.extend(plist_values(value))
    elif isinstance(item, list):
        for value in item:
            values.extend(plist_values(value))
    return values


def scan(stream, total, chunk_size=1024*1024):
    need(total >= 0 and chunk_size > 0, 'invalid bounds')
    digest = hashlib.sha256()
    offset = records = regular = plist_oversize = 0
    matches = []
    names = set()

    def read_exact(n):
        nonlocal offset
        need(0 <= n <= total-offset, 'archive extent differs')
        parts = []
        while n:
            data = stream.read(min(n, chunk_size))
            need(bool(data), 'truncated archive')
            digest.update(data)
            offset += len(data)
            n -= len(data)
            parts.append(data)
        return b''.join(parts)

    while True:
        header = read_exact(76)
        need(header[:6] == b'070707', 'unsupported odc header')
        try:
            mode = int(header[18:24], 8)
            namesize = int(header[59:65], 8)
            size = int(header[65:76], 8)
        except ValueError as exc:
            raise ValueError('invalid odc fields') from exc
        need(1 <= namesize <= 4096, 'invalid filename extent')
        name_bytes = read_exact(namesize)
        need(name_bytes.endswith(b'\0') and b'\0' not in name_bytes[:-1], 'invalid filename')
        name = name_bytes[:-1].decode('utf-8')
        records += 1
        if name == 'TRAILER!!!':
            need(size == 0, 'trailer payload')
            break
        need(name not in names, 'duplicate archive member')
        names.add(name)
        is_regular = stat.S_ISREG(mode)
        if is_regular:
            regular += 1
        is_plist = is_regular and name.endswith('.plist')
        capture_plist = is_plist and size <= PLIST_LIMIT
        if is_plist and not capture_plist:
            plist_oversize += 1
        member_digest = hashlib.sha256()
        counts = dict.fromkeys(PATTERNS, 0)
        tail = b''
        plist_chunks = []
        remaining = size
        while remaining:
            block = read_exact(min(remaining, chunk_size))
            remaining -= len(block)
            member_digest.update(block)
            if is_regular:
                combined = tail + block
                for label, pattern in PATTERNS.items():
                    counts[label] += combined.count(pattern) - tail.count(pattern)
                tail = combined[-(max(map(len, PATTERNS.values()))-1):]
                if capture_plist:
                    plist_chunks.append(block)
        if is_regular and any(counts.values()):
            row = {'name': name, 'size': size, 'sha256': member_digest.hexdigest(), 'literal_counts': counts,
                   'plist_parse': 'not_plist', 'plist_key_values': []}
            if is_plist:
                if not capture_plist:
                    row['plist_parse'] = 'oversize'
                else:
                    try:
                        row['plist_key_values'] = plist_values(plistlib.loads(b''.join(plist_chunks)))
                        row['plist_parse'] = 'ok'
                    except Exception as exc:
                        row['plist_parse'] = 'error:' + type(exc).__name__
            matches.append(row)
            need(len(matches) <= 5000, 'match limit exceeded')
    trailing = total-offset
    while offset < total:
        read_exact(min(chunk_size, total-offset))
    need(not stream.read(1), 'archive grew during scan')
    return {'archive_sha256': digest.hexdigest(), 'archive_bytes': offset, 'records': records,
            'regular_members': regular, 'trailing_bytes': trailing, 'oversize_plists': plist_oversize, 'matches': matches}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    need(args.out.parent.is_dir() and not args.out.exists(), 'fresh output required')
    need(args.archive.stat().st_size == HIGH_SIZE, 'archive size differs')
    with args.archive.open('rb') as stream:
        result = scan(stream, HIGH_SIZE)
    need(result['archive_sha256'] == HIGH_SHA and result['records'] == 86095, 'archive identity differs')
    result.update(status='PASS_FULL_REGULAR_MEMBER_LITERAL_SURVEY', property_name=KEY,
                  scope='All regular members in retained High Sierra update payload; ASCII and UTF-16 byte sequences; no decompression of nested files',
                  dynamic_producers_excluded=False, complete_installation_searched=False,
                  vendor_execution=False, GPU_execution=False, system_modified=False,
                  auditor_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    with args.out.open('x') as out:
        json.dump(result, out, indent=2, sort_keys=True)
        out.write('\n')
    print(json.dumps({'status': result['status'], 'regular_members': result['regular_members'],
                      'matching_members': len(result['matches']), 'archive_sha256': result['archive_sha256']}))


if __name__ == '__main__':
    main()
