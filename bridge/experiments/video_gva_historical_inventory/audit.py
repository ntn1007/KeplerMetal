#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read a pinned historical Apple odc archive; never extract or execute it."""
import argparse
import hashlib
import json
import plistlib
import re
import stat
from pathlib import Path

EXPECTED_SHA = 'b48e6eaaacb86400dfc9e84ed85a8df666baa24af7ca3a632b73607a1d2f4cc6'
EXPECTED_SIZE = 5801167872
NVIDIA = re.compile(r'^\./System/Library/Extensions/((?:GeForce|NVDA)[^/]*\.(?:kext|bundle))/Contents/(Info\.plist|MacOS/[^/]+)$')
CONTROLS = {
    './System/Library/Extensions/AppleIntelBDWGraphics.kext/Contents/Info.plist': 'Gen8',
    './System/Library/Extensions/AppleIntelHD3000Graphics.kext/Contents/Info.plist': 'Gen6',
    './System/Library/Extensions/AppleIntelHD4000Graphics.kext/Contents/Info.plist': 'Gen7',
    './System/Library/Extensions/AppleIntelHD5000Graphics.kext/Contents/Info.plist': 'Gen75',
    './System/Library/Extensions/AppleIntelKBLGraphics.kext/Contents/Info.plist': 'Gen95',
    './System/Library/Extensions/AppleIntelSKLGraphics.kext/Contents/Info.plist': 'Gen9',
    './System/Library/Extensions/AMDRadeonX5000.kext/Contents/Info.plist': 'AMDU7V4',
}


def need(ok, reason):
    if not ok:
        raise ValueError(reason)


def keys(value, key):
    found = []
    if isinstance(value, dict):
        for name, child in value.items():
            if name == key:
                found.append(child)
            found.extend(keys(child, key))
    elif isinstance(value, list):
        for child in value:
            found.extend(keys(child, key))
    return found


def scan(stream, total):
    """Stream and hash every archive byte; retain only bounded matched members."""
    digest = hashlib.sha256()
    offset = 0
    rows = []
    controls = {}
    selected = set()
    records = 0

    def read_exact(amount, keep):
        nonlocal offset
        need(isinstance(amount, int) and 0 <= amount <= total - offset, 'archive extent differs')
        remaining = amount
        chunks = []
        while remaining:
            data = stream.read(min(remaining, 1024 * 1024))
            need(bool(data), 'truncated archive')
            digest.update(data)
            offset += len(data)
            remaining -= len(data)
            if keep:
                chunks.append(data)
        return b''.join(chunks) if keep else b''

    while True:
        head = read_exact(76, True)
        need(head[:6] == b'070707', 'unsupported cpio format or missing trailer')
        try:
            mode = int(head[18:24], 8)
            namesize = int(head[59:65], 8)
            size = int(head[65:76], 8)
        except ValueError as exc:
            raise ValueError('invalid odc numeric field') from exc
        need(1 <= namesize <= 4096, 'invalid filename extent')
        raw_name = read_exact(namesize, True)
        need(raw_name.endswith(b'\0') and b'\0' not in raw_name[:-1], 'invalid filename')
        try:
            name = raw_name[:-1].decode('utf-8')
        except UnicodeDecodeError as exc:
            raise ValueError('invalid filename encoding') from exc
        records += 1
        if name == 'TRAILER!!!':
            need(size == 0, 'invalid trailer')
            break
        match = NVIDIA.fullmatch(name)
        wanted = bool(match) or name in CONTROLS
        if wanted:
            need(name not in selected and stat.S_ISREG(mode) and 0 < size <= 64 * 1024 * 1024,
                 'selected entry is duplicate, nonregular or unsupported size')
            selected.add(name)
        payload = read_exact(size, wanted)
        if not wanted:
            continue
        if name in CONTROLS:
            values = keys(plistlib.loads(payload), 'IOGVACodec')
            need(values and all(type(v) is str and v == CONTROLS[name] for v in values), 'positive control differs')
            controls[name] = {'sha256': hashlib.sha256(payload).hexdigest(), 'value': CONTROLS[name], 'matches': len(values)}
        elif match:
            category = 'plist' if match.group(2) == 'Info.plist' else 'binary'
            row = {'name': name, 'kind': category, 'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}
            if category == 'plist':
                row['codec_key_paths'] = len(keys(plistlib.loads(payload), 'IOGVACodec'))
            else:
                row['ascii_occurrences'] = payload.count(b'IOGVACodec')
                row['utf16le_occurrences'] = payload.count('IOGVACodec'.encode('utf-16le'))
                row['utf16be_occurrences'] = payload.count('IOGVACodec'.encode('utf-16be'))
            rows.append(row)
    trailing = total - offset
    read_exact(trailing, False)
    need(not stream.read(1), 'archive grew during scan')
    return {'archive_sha256': digest.hexdigest(), 'archive_bytes': offset, 'records': records,
            'trailing_bytes': trailing, 'nvidia_members': rows, 'controls': controls}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    need(a.out.parent.is_dir() and not a.out.exists(), 'fresh output required')
    need(a.archive.stat().st_size == EXPECTED_SIZE, 'archive size differs')
    with a.archive.open('rb') as stream:
        result = scan(stream, EXPECTED_SIZE)
    need(result['archive_sha256'] == EXPECTED_SHA and result['records'] == 86095, 'archive identity differs')
    rows = result['nvidia_members']
    plists = [x for x in rows if x['kind'] == 'plist']
    binaries = [x for x in rows if x['kind'] == 'binary']
    need(len(plists) == 15 and len(binaries) == 19 and set(result['controls']) == set(CONTROLS), 'inventory differs')
    need(all(x['codec_key_paths'] == 0 for x in plists) and
         all(x['ascii_occurrences'] == x['utf16le_occurrences'] == x['utf16be_occurrences'] == 0 for x in binaries),
         'unexpected match; investigate rather than silently generalize')
    result.update(status='PASS_BOUNDED_HISTORICAL_INVENTORY', source='retained macOS 10.13.6 Combo update payload',
                  scope='GeForce/NVDA extension plists and selected Mach-O members only; not all OS files or runtime paths',
                  nvidia_plist_count=len(plists), nvidia_binary_count=len(binaries),
                  nvidia_codec_value_identified=False, dynamically_produced_property_excluded=False,
                  literal_absence_proves_no_producer=False, hardware_video_execution_proved=False,
                  vendor_execution=False, GPU_execution=False, system_modified=False,
                  auditor_source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    with a.out.open('x') as f:
        json.dump(result, f, indent=2, sort_keys=True)
        f.write('\n')
    print(json.dumps({'status': result['status'], 'plists': len(plists), 'binaries': len(binaries),
                      'archive_sha256': result['archive_sha256'], 'GPU_execution': False}))


if __name__ == '__main__':
    main()
