#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit a pinned NVIDIA RM control table and nested-copy path offline."""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'tools'))
from compare_video_profile import file_bytes

IMAGE = '36396eaecd68ddbb0482f019f38ce55d01b10379ca829da7f19b3bd8f3e26808'
BUNDLE = 'd5b64de06f54e032dea12d5a38482596bcd2239c1d61cd58302847754f66e379'
TABLE = 'c3f80a559854a4835ae18324b7880b8dba480be5ff79d51b7bb833abb37765c1'
FUNCTIONS = {
  0x12ccd4: (17, 'aaf3b9f3ab22312e9859f80c8a220d074b32d1fb2df1c2cdb669b811ee1357ad', 'ev_95ab09de203d6ef0e18109ae01f3921eaae7dcc990580c23f385fb70c801219f'),
  0x4537f: (170, '0fd991271bd6e7fe6dad42d6357c708b99b8104971cfb0a8aecc1e1e720b6c94', 'ev_e877324aa64f19931b1e917dd95afbc55660805391cbc46eb55e4b46acca5fe8'),
  0x451c3: (438, 'e33aca3db82f62d29acf028ff51f30bf25c75e6a727435f9a6a84c98741be454', 'ev_c3c7082591044b59b3a4e235bdaab0f0fd57d241f2a5b68bef437e799f264f0b'),
  0x12e0d9: (35, '7e56d6e1c6075484ab365e76476ef586ac7f34b0ddc13de2efa20e6b5d0d305f', 'ev_0c0ce7dff6654df51fcd14cfff582adbcec2b0f02b42421ce62b415c4f1d772f'),
  0x12ed71: (154, 'e7fba355f89e08c7a38fea8d5ea27452eae08fb040a9174497c951fe0daf5999', 'ev_2cbad200ea1cdc045e72fb11663691b42a2abbf9b9fee6f2977434383771f837'),
  0x3307c: (477, '9b3a24d502b3535591c292777dda581c5f3860d24d08ff89b916ea044ef6e56d', 'ev_cb4a5cc906cde95a5ce61dc84cc3b662a1232462520c63e20b65fadf0a6648ac'),
  0x33259: (82, '6eb9e1ceea4e8b3741bee3cb6b3b350ec0b333c68150cb2bce01941c6e60e10b', 'ev_0eecaa7f5903405ab3392dc3be984c65eadb9cc422f6787e7da72e23df0eda09'),
  0x332ab: (126, 'f1d3384ae57095c4357d4a22a4ded1adbe8577343b8350fe7a3d0823ba233fb4', 'ev_994214d77a3c376b2bbdd38143a9218eba8c53e9a533fedecffd4ebd5e1a8c4b'),
  0x6c35: (511, '03a5eda090fd17e29920713e01ecd33a25fc67c65c9b1150ed535f930cc922af', 'ev_cddd036406e685707b38676d0ab893c5e2d215dc3964f6bfdd44895bd50c6430'),
  0x6e34: (511, 'b10b557d0e34858051412a8555d8bcf3012f465fb10239eaffd6d2ff899d9fb4', 'ev_2f37d68bece041e56cdc25af607560173a43993a030c3c1f730e4c537a38209a'),
}

def need(value, reason):
    if not value:
        raise ValueError(reason)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def check_table(data):
    need(len(data) == 82 * 16 and digest(data) == TABLE, 'pinned table')
    rows = [struct.unpack_from('<IIQ', data, i * 16) for i in range(82)]
    need(all(row[2] != 0 for row in rows[:81]) and rows[81][2] == 0, 'table termination')
    hits = [(i, x) for i, x in enumerate(rows[:81]) if x[0] == 0x800201]
    need(hits == [(62, (0x800201, 0x30010, 0x12e0d9))], 'unique class-list entry')

def local_relocation(data, address):
    count, extent = struct.unpack_from('<II', data, 16)
    need(count <= 4096 and 32 + extent <= len(data), 'bounded commands')
    off, found = 32, []
    for _ in range(count):
        command, size = struct.unpack_from('<II', data, off)
        need(size >= 8 and off + size <= 32 + extent, 'command bounds')
        if command == 11:
            need(size == 80, 'dysymtab size')
            vals = struct.unpack_from('<20I', data, off)
            rel, entries = vals[18:20]
            need(rel + 8 * entries <= len(data), 'relocation bounds')
            for i in range(entries):
                site, flags = struct.unpack_from('<II', data, rel + 8 * i)
                if site == address:
                    found.append(flags)
        off += size
    need(off == 32 + extent and found == [0x06000001], 'local text relocation')

def edge(image, source, target, opcode=0xe8):
    _, b = file_bytes(image, source, 5)
    need(b[0] == opcode and source + 5 + struct.unpack_from('<i', b, 1)[0] == target,
         'edge ' + hex(source))

def inspect(image, bundle):
    need(digest(image) == IMAGE and digest(bundle) == BUNDLE, 'image/evidence pin')
    records = {r['evidence_id']: r for r in json.loads(bundle)['records']}
    functions = {}
    for address, (size, expected, evidence) in FUNCTIONS.items():
        offset, code = file_bytes(image, address, size)
        need(digest(code) == expected, 'body ' + hex(address))
        record = records[evidence]
        body = record['normalized_result']['procedure']
        need(record['subject']['digest']['sha256'] == IMAGE and body['address'] == hex(address)
             and body['body']['total_bytes'] == size and body['body']['contains_entry']
             and not body['body']['non_contiguous'], 'REA body ' + hex(address))
        functions[hex(address)] = {'file_offset': offset, 'bytes': size,
                                   'sha256': expected, 'evidence_id': evidence}
    _, table = file_bytes(image, 0x28a370, 82 * 16)
    check_table(table)
    local_relocation(image, 0x28a758)
    for source, target, op in [(0x12cce0, 0x4537f, 0xe9), (0x4539f, 0x451c3, 0xe8),
                               (0x453db, 0x3307c, 0xe8), (0x12e0f7, 0x12ed71, 0xe9),
                               (0x12edbe, 0x3307c, 0xe8), (0x12edf2, 0x332ab, 0xe8),
                               (0x3315e, 0x33259, 0xe8), (0x33212, 0x7033, 0xe8),
                               (0x332e0, 0x704f, 0xe8)]:
        edge(image, source, target, op)
    return {'status': 'PASS_STATIC_NESTED_COPY', 'image_sha256': IMAGE, 'rea_sha256': BUNDLE,
            'functions': functions, 'table_sha256': TABLE, 'table_entry': 62,
            'command': '0x800201', 'entry_flags_and_size': '0x30010',
            'raw_handler': '0x12e0d9', 'handler_local_relocation': '0x28a758',
            'scope': 'File-backed observations only; user-route reachability, handles, live behavior, backend bounds and hardware video remain unqualified.',
            'private_RM_calls': 0, 'GPU_dispatches': 0, 'system_modified': False}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--image', type=Path, required=True)
    p.add_argument('--rea', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    need(args.out.parent.is_dir() and not args.out.exists(), 'fresh output required')
    result = inspect(args.image.read_bytes(), args.rea.read_bytes())
    with args.out.open('x') as f:
        json.dump(result, f, indent=2, sort_keys=True)
        f.write('\n')
    print(json.dumps(result, sort_keys=True))

if __name__ == '__main__':
    main()
