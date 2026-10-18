#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Hash-check bounded private captures and map calls/CF keys offline.

Creates private analysis data only. It never loads or executes vendor code.
Static import names and decoded constant keys are not runtime call evidence.
"""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import struct
import subprocess

from inspect_video_cache import Cache, require, sha, stub_symbol

ROOT = Path(__file__).resolve().parents[1]


def constant_string(cache, address):
    raw = cache.read(address, 32)
    flags, count = struct.unpack_from('<Q', raw, 8)[0], struct.unpack_from('<Q', raw, 24)[0]
    require(flags == 0x7c8 and count <= 1024, 'supported constant ASCII CFString')
    pointer = cache.pointer_v2(address + 16)
    data = cache.read(pointer, count + 1)
    require(data[-1] == 0, 'CFString terminator')
    return data[:-1].decode('ascii')


def analyze(args):
    out = args.out.resolve()
    out.relative_to(ROOT / 'results')
    require(1 <= len(args.capture) <= 8, 'one to eight captures')
    cache = Cache(args.cache.resolve())
    out.mkdir(exist_ok=False)
    sources = [Path(__file__), Path(__file__).with_name('inspect_video_cache.py'),
               Path(__file__).with_name('video_region_analysis_object.py')]
    for source in sources:
        shutil.copyfile(source, out / source.name)
    records = []
    for index, capture in enumerate(args.capture):
        capture = capture.resolve()
        metadata = capture / 'metadata.json'
        m = json.loads(metadata.read_text())
        r = m['region']
        require(m['status'] == 'PASS' and m['runtime_UUID_matched']
                and m['region_captured_privately'] and not m['native_program_executed']
                and m['image']['UUID'] == 'e7231bea63883d0a95c0a93ce970b96b'
                and r['boundary_source'] == 'LC_FUNCTION_STARTS'
                and 0 < r['bytes'] <= 65536
                and sha(capture / 'function-region.private.bin') == r['SHA256'], 'capture identity')
        folder = out / ('region-%02d' % index)
        folder.mkdir()
        obj = folder / 'analysis.private.o'
        wrap = ['python3', str(out / 'video_region_analysis_object.py'), '--metadata', str(metadata), '--out', str(obj)]
        built = subprocess.run(wrap, capture_output=True, check=True, timeout=30)
        (folder / 'wrapper.json').write_bytes(built.stdout)
        disassemble = ['xcrun', 'llvm-objdump', '--disassemble', '--no-show-raw-insn', str(obj)]
        q = subprocess.run(disassemble, capture_output=True, check=True, timeout=30)
        (folder / 'disassembly.private.txt').write_bytes(q.stdout)
        calls, branches, refs = [], [], []
        for line in q.stdout.decode().splitlines():
            match = re.search(r'^\s*([0-9a-f]+):\s+(callq|jmp)\s+0x([0-9a-f]+)', line)
            if match:
                site, target = int(match[1], 16), int(match[3], 16)
                row = {'site_VM': site, 'target_VM': target, 'site_image_offset': site - m['image_base_VM'],
                       'target_image_offset': target - m['image_base_VM'],
                       'static_binding': stub_symbol(cache, m['image'], target)}
                if match[2] == 'callq':
                    row['return_site_image_offset'] = site + 5 - m['image_base_VM']
                    calls.append(row)
                else:
                    branches.append(row)
            match = re.search(r'^\s*([0-9a-f]+):.*# 0x([0-9a-f]+)', line)
            if not match:
                continue
            site, address = int(match[1], 16), int(match[2], 16)
            for kind in ('direct_CFString', 'global_CFString_pointer'):
                try:
                    object_ = address if kind == 'direct_CFString' else cache.pointer_v2(address)
                    value = constant_string(cache, object_)
                except (ValueError, StopIteration, UnicodeError):
                    continue
                refs.append({'site_image_offset': site - m['image_base_VM'], 'referenced_VM': address,
                             'kind': kind, 'string': value})
                break
        records.append({'capture': str(capture), 'metadata_SHA256': sha(metadata),
            'region_SHA256': r['SHA256'], 'region_bytes': r['bytes'],
            'start_image_offset': r['start_VM'] - m['image_base_VM'],
            'wrapper_argv': wrap, 'container_SHA256': sha(obj), 'disassembly_argv': disassemble,
            'disassembly_SHA256': hashlib.sha256(q.stdout).hexdigest(), 'calls': calls,
            'direct_jumps': branches, 'constant_references': refs})
    parts = [{**cache.parts[i], 'SHA256': sha(cache.parts[i]['path'])} for i in sorted(cache.used)]
    report = {'status': 'STATIC_ONLY', 'records': records, 'cache_parts_read': parts,
        'source_hashes': {source.name: sha(out / source.name) for source in sources},
        'private_ABIs_established': False, 'vendor_program_executed': False,
        'runtime_branch_proved': False, 'system_modified': False}
    (out / 'analysis.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': 'STATIC_ONLY', 'regions': len(records),
        'analysis_SHA256': sha(out / 'analysis.json'), 'vendor_program_executed': False}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--capture', type=Path, action='append', required=True)
    parser.add_argument('--out', type=Path, required=True)
    analyze(parser.parse_args())


if __name__ == '__main__':
    main()
