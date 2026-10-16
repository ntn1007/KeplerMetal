#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Wrap a hash-checked private x86_64 region for LLVM offline disassembly.

The ELF relocatable container has no program headers, loader, entry point,
relocations or vendor symbols. It is analysis data, never an executable dylib.
Original cache files are read-only and the wrapper is never published.
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    m = json.loads(args.metadata.read_text())
    region = m['region']
    data = args.metadata.with_name('function-region.private.bin').read_bytes()
    if not (m['status'] == 'PASS' and m['region_captured_privately']
            and region['boundary_source'] == 'LC_FUNCTION_STARTS'
            and 0 < len(data) == region['bytes'] <= 65536
            and hashlib.sha256(data).hexdigest() == region['SHA256']
            and region['start_VM'] + len(data) == region['end_VM']):
        raise ValueError('Bounded private region provenance mismatch')
    strings = b'\0.text\0.shstrtab\0'
    text_offset = 64
    strings_offset = text_offset + len(data)
    sections_offset = (strings_offset + len(strings) + 7) & ~7
    identity = b'\x7fELF' + bytes([2, 1, 1, 0]) + b'\0'*8
    header = struct.pack('<16sHHIQQQIHHHHHH', identity, 1, 62, 1, 0, 0,
                         sections_offset, 0, 64, 0, 0, 64, 3, 2)
    null = b'\0'*64
    text = struct.pack('<IIQQQQIIQQ', 1, 1, 6, region['start_VM'], text_offset, len(data), 0, 0, 16, 0)
    names = struct.pack('<IIQQQQIIQQ', 7, 3, 0, 0, strings_offset, len(strings), 0, 0, 1, 0)
    output = header + data + strings
    output += b'\0'*(sections_offset-len(output)) + null + text + names
    with args.out.open('xb') as f:
        f.write(output)
    print(json.dumps({'status': 'PASS', 'kind': 'ELF64_ET_REL_analysis_container',
                      'container_SHA256': hashlib.sha256(output).hexdigest(),
                      'region_SHA256': region['SHA256'], 'program_executed': False,
                      'source_function_identity_proved': False}))


if __name__ == '__main__':
    main()
