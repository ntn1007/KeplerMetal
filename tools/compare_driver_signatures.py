#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only comparison of thin x86_64 Mach-O files and embedded signatures.

Reports byte identity, not certificate authenticity or runtime compatibility.
It never updates an allowlist or prints/copies proprietary program bytes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct


def sha(data):
    return hashlib.sha256(data).hexdigest()


def signature(data):
    def require(condition, message):
        if not condition: raise ValueError(message)
    require(32 <= len(data) <= 64*1024**2, 'Unsupported file size')
    header = struct.unpack_from('<8I', data)
    require(header[0] == 0xfeedfacf and header[1] == 0x1000007, 'Requires thin x86_64 Mach-O')
    count, size = header[4:6]
    end = 32 + size
    require(count <= 4096 and end <= len(data), 'Invalid load-command bounds')
    offset = 32; ranges = []
    for _ in range(count):
        require(offset+8 <= end, 'Truncated load command')
        cmd, length = struct.unpack_from('<II', data, offset)
        require(length >= 8 and length % 8 == 0 and offset+length <= end, 'Invalid load-command size')
        if cmd == 0x1d:
            require(length == 16, 'Invalid code-signature command')
            ranges.append(struct.unpack_from('<II', data, offset+8))
        offset += length
    require(offset == end and len(ranges) == 1, 'Requires exactly one embedded signature')
    start, length = ranges[0]
    require(start >= end and length >= 12 and start+length <= len(data), 'Invalid signature range')
    magic, used, count = struct.unpack_from('>III', data, start)
    require(magic == 0xfade0cc0 and 12 <= used <= length and count <= 64 and 12+8*count <= used, 'Invalid signature SuperBlob')
    blobs = {}; intervals = []
    for i in range(count):
        kind, relative = struct.unpack_from('>II', data, start+12+8*i)
        require(kind not in blobs and relative >= 12+8*count and relative+8 <= used, 'Invalid signature index')
        blob_magic, blob_size = struct.unpack_from('>II', data, start+relative)
        require(blob_size >= 8 and relative+blob_size <= used, 'Invalid signature blob bounds')
        require(all(relative+blob_size <= a or relative >= b for a,b in intervals), 'Overlapping signature blobs')
        intervals.append((relative,relative+blob_size))
        blobs[kind] = dict(offset=start+relative,size=blob_size,magic=blob_magic,
            SHA256=sha(data[start+relative:start+relative+blob_size]))
    require(0 in blobs and blobs[0]['magic'] == 0xfade0c02, 'Missing CodeDirectory')
    require(0x10000 in blobs and blobs[0x10000]['magic'] == 0xfade0b01, 'Missing CMS wrapper')
    return dict(offset=start,size=length,blobs=blobs,
        outside_signature_SHA256=sha(data[:start]+data[start+length:]))


def compare(a, b):
    left, right = signature(a), signature(b)
    def without_cms(data, parsed):
        cms = parsed['blobs'][0x10000]
        begin, end = cms['offset']+8, cms['offset']+cms['size']
        return data[:begin]+b'\0'*(end-begin)+data[end:]
    layout = lambda p: (p['offset'],p['size'],{k:(v['offset'],v['size'],v['magic']) for k,v in p['blobs'].items()})
    same_layout = layout(left) == layout(right)
    cms_only = same_layout and without_cms(a,left) == without_cms(b,right)
    identical = a == b
    return dict(classification='IDENTICAL' if identical else ('CMS_SIGNATURE_ONLY' if cms_only else 'CONTENT_CHANGED'),
        left_SHA256=sha(a),right_SHA256=sha(b),left=left,right=right,
        equal_length=len(a)==len(b),different_bytes=sum(x!=y for x,y in zip(a,b))+abs(len(a)-len(b)),
        outside_signature_identical=a[:left['offset']]+a[left['offset']+left['size']:] == b[:right['offset']]+b[right['offset']+right['size']:],
        CodeDirectory_identical=left['blobs'][0]['SHA256']==right['blobs'][0]['SHA256'],
        signature_authenticity_checked=False,runtime_compatibility_proved=False,GPU_execution=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('reference',type=Path); p.add_argument('candidate',type=Path)
    a = p.parse_args()
    print(json.dumps(compare(a.reference.read_bytes(),a.candidate.read_bytes()),indent=2))


if __name__ == '__main__': main()
