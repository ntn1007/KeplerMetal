#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Hash a bounded pbzx stream and its decoded bytes without writing them."""
import argparse
import hashlib
import json
import lzma
import struct
from pathlib import Path


def verify(stream, expected_digest, expected_size):
    compressed = hashlib.sha256(); decoded = hashlib.sha256(); total = chunks = 0
    def exact(n):
        data = stream.read(n)
        if len(data) != n: raise ValueError('truncated pbzx')
        compressed.update(data)
        return data
    if exact(4) != b'pbzx': raise ValueError('not pbzx')
    flags = struct.unpack('>Q', exact(8))[0]
    while flags & 0x1000000:
        flags, length = struct.unpack('>QQ', exact(16)); chunks += 1
        if not 0 < length <= 67108864: raise ValueError('invalid chunk size')
        data = exact(length)
        block = lzma.decompress(data, format=lzma.FORMAT_XZ, memlimit=268435456) if data.startswith(b'\xfd7zXZ\0') else data
        if len(block) > 33554432: raise ValueError('decoded chunk too large')
        decoded.update(block); total += len(block)
    if not chunks or stream.read(1): raise ValueError('empty stream or trailing bytes')
    if total != expected_size or decoded.hexdigest() != expected_digest:
        raise ValueError('decoded payload does not match survey')
    return {'compressed_sha256': compressed.hexdigest(), 'decoded_sha256': decoded.hexdigest(), 'decoded_bytes': total, 'chunks': chunks}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--payload', type=Path, required=True)
    p.add_argument('--survey', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if not a.out.parent.is_dir() or a.out.exists(): raise ValueError('fresh output required')
    survey_bytes=a.survey.read_bytes(); survey=json.loads(survey_bytes)
    if survey['status']!='PASS_SIERRA_REGULAR_MEMBER_LITERAL_SURVEY': raise ValueError('survey differs')
    with a.payload.open('rb') as f: result=verify(f,survey['archive_sha256'],survey['archive_bytes'])
    result.update(status='PASS_PBZX_DECODE_IDENTITY',survey_sha256=hashlib.sha256(survey_bytes).hexdigest(),
                  payload_bytes=a.payload.stat().st_size,signature_rechecked=False,
                  vendor_execution=False,GPU_execution=False,system_modified=False,
                  verifier_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'status':result['status'],'chunks':result['chunks'],'decoded_sha256':result['decoded_sha256']}))


if __name__ == '__main__': main()
