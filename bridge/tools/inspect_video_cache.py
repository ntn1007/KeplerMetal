#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read one named x86_64 cache image's metadata and bounded function starts.

No image is loaded or executed. Optional region bytes are private local analysis
data, not a reconstructed/loadable dylib and never publication inputs.
Layout reference: apple-oss-distributions/dyld fd8d0c4d52320ebf64db34f3cb280310d905c5ae,
include/mach-o/dyld_cache_format.h. Uses only the public mapping table prefix.
"""
from pathlib import Path
import argparse
import bisect
import hashlib
import json
import re
import struct

ROOT = Path(__file__).resolve().parents[1]
MAX_READ = 16 * 1024 * 1024


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for data in iter(lambda: f.read(1024*1024), b''):
            h.update(data)
    return h.hexdigest()


def cstring(data, start, end):
    require(0 <= start < end <= len(data), 'string bounds')
    stop = data.find(b'\0', start, end)
    require(stop >= 0, 'unterminated string')
    return data[start:stop].decode('utf-8')


def uleb(data, offset):
    value = 0
    for shift in range(0, 70, 7):
        require(offset < len(data), 'truncated ULEB')
        byte = data[offset]
        offset += 1
        require(shift < 63 or byte <= 1, 'ULEB overflow')
        value |= (byte & 127) << shift
        if not byte & 128:
            return value, offset
    raise ValueError('ULEB overflow')


class Cache:
    def __init__(self, base):
        self.parts, self.mappings, self.used = [], [], set()
        paths = [base] + sorted(p for p in base.parent.glob(base.name + '.*')
                               if re.fullmatch(re.escape(base.name) + r'\.\d{2}', p.name))
        for path in paths:
            with path.open('rb') as f:
                header = f.read(104)
                require(header[:4] == b'dyld' and b'x86_64' in header[:16], 'x86_64 cache magic')
                offset, count = struct.unpack_from('<II', header, 16)
                size = path.stat().st_size
                require(0 < count < 128 and offset + 32*count <= size, 'mapping table bounds')
                f.seek(offset)
                table = f.read(32*count)
            part = {'name': path.name, 'path': str(path), 'bytes': size,
                    'UUID': header[88:104].hex(), 'header_SHA256': hashlib.sha256(header).hexdigest(),
                    'mapping_table_SHA256': hashlib.sha256(table).hexdigest()}
            self.parts.append(part)
            for i in range(count):
                address, length, fileoff, maximum, initial = struct.unpack_from('<QQQII', table, 32*i)
                require(length > 0 and fileoff + length <= size, 'mapping file extent')
                self.mappings.append({'address': address, 'size': length, 'file_offset': fileoff,
                                      'max_protection': maximum, 'initial_protection': initial, 'part': len(self.parts)-1})
        self.mappings.sort(key=lambda m: m['address'])
        for a, b in zip(self.mappings, self.mappings[1:]):
            require(a['address'] + a['size'] <= b['address'], 'ambiguous overlapping cache mappings')

    def read(self, address, size):
        require(0 <= size <= MAX_READ, 'bounded read size')
        result = bytearray()
        while size:
            matches = [m for m in self.mappings if m['address'] <= address < m['address'] + m['size']]
            require(len(matches) == 1, 'unmapped/ambiguous VM address')
            m = matches[0]
            count = min(size, m['address'] + m['size'] - address)
            part = self.parts[m['part']]
            with Path(part['path']).open('rb') as f:
                f.seek(m['file_offset'] + address - m['address'])
                data = f.read(count)
            require(len(data) == count, 'short cache read')
            self.used.add(m['part'])
            result.extend(data)
            size -= count
            address += count
        return bytes(result)

    def pointer_v2(self, address):
        """Decode only a slot verified to belong to a version-2 rebase chain."""
        mapping = next(m for m in self.mappings if m['address'] <= address < m['address'] + m['size'])
        path = Path(self.parts[mapping['part']]['path'])
        with path.open('rb') as f:
            header = f.read(320)
            tableoff, count = struct.unpack_from('<II', header, 312)
            require(0 < count < 128 and tableoff + 56*count <= path.stat().st_size, 'slide mapping table')
            f.seek(tableoff)
            table = f.read(56*count)
            matches = []
            for i in range(count):
                row = struct.unpack_from('<QQQQQQII', table, 56*i)
                if row[0] <= address < row[0]+row[1]:
                    matches.append(row)
            require(len(matches) == 1, 'unique slide mapping')
            start, length, fileoff, slideoff, slidesize, _, _, _ = matches[0]
            require(40 <= slidesize <= MAX_READ and slideoff + slidesize <= path.stat().st_size,
                    'slide info extent')
            f.seek(slideoff)
            slide = f.read(slidesize)
        version, page, starts_off, starts_count, extras_off, extras_count, mask, add = struct.unpack_from('<IIIIIIQQ', slide)
        require(version == 2 and page > 0 and page & (page-1) == 0 and mask != 0, 'supported slide v2')
        require(starts_off + 2*starts_count <= len(slide), 'page starts extent')
        index, position = divmod(address-start, page)
        require(index < starts_count and position+8 <= page, 'pointer page position')
        entry, = struct.unpack_from('<H', slide, starts_off + 2*index)
        require(entry != 0x4000 and not entry & 0x8000, 'single v2 chain required; extra/no-rebase pages refused')
        offset, shift = entry*4, (mask & -mask).bit_length()-1-2
        require(0 <= shift <= 62, 'delta shift')
        for _ in range(page//4):
            require(offset+8 <= page, 'rebase chain page bound')
            raw, = struct.unpack('<Q', self.read(start + index*page + offset, 8))
            if offset == position:
                value = raw & (~mask & ((1 << 64)-1))
                return value+add if value else 0
            delta = (raw & mask) >> shift
            if not delta:
                break
            offset += delta
        raise ValueError('Requested slot is not a verified rebase-chain member')


def image_map(path, image):
    active, segments = False, []
    for line in path.read_text().splitlines():
        if line.startswith('/'):
            if active:
                break
            active = line == image
        elif active:
            match = re.fullmatch(r'\s+(\S+)\s+(0x[0-9A-Fa-f]+) -> (0x[0-9A-Fa-f]+)', line)
            if match:
                segments.append({'name': match[1], 'start': int(match[2], 16), 'end': int(match[3], 16)})
    require(segments and segments[0]['name'] == '__TEXT', 'exact image absent from map')
    return segments


def inspect(cache, base, expected_name):
    head = cache.read(base, 32)
    magic, cpu, _, _, count, size, _, _ = struct.unpack('<IiiIIIII', head)
    require(magic == 0xfeedfacf and cpu == 0x1000007 and count <= 4096 and size <= 1024*1024, 'Mach-O x86_64 header')
    data, offset = cache.read(base + 32, size), 0
    result = {'UUID': None, 'install_name': None, 'current_version': None,
              'segments': [], 'sections': [], 'build_versions': [], 'dependencies': []}
    linkdata = {}
    for _ in range(count):
        require(offset + 8 <= len(data), 'load command prefix')
        command, length = struct.unpack_from('<II', data, offset)
        require(8 <= length <= len(data) - offset, 'load command extent')
        c = data[offset:offset+length]
        if command == 0x1b:
            require(length >= 24, 'UUID command')
            result['UUID'] = c[8:24].hex()
        elif command in [0xd, 0xc, 0x80000018, 0x8000001f, 0x20, 0x80000023]:
            require(length >= 24, 'dylib command')
            nameoff, _, current, compatibility = struct.unpack_from('<IIII', c, 8)
            require(nameoff >= 24, 'dylib name prefix')
            name = cstring(c, nameoff, length)
            if command == 0xd:
                result.update(install_name=name, current_version=current, compatibility_version=compatibility)
            else:
                result['dependencies'].append({'name': name, 'command': command})
        elif command == 0x19:
            require(length >= 72, 'segment command')
            name, vm, vmsize, fileoff, filesize, maximum, initial, sections, flags = struct.unpack_from('<16sQQQQiiII', c, 8)
            require(72 + 80*sections <= length, 'section table')
            result['segments'].append({'name': name.rstrip(b'\0').decode(), 'VM_address': vm,
                'VM_size': vmsize, 'file_offset': fileoff, 'file_size': filesize})
            for j in range(sections):
                pos = 72 + j*80
                section, segment, address, section_size = struct.unpack_from('<16s16sQQ', c, pos)
                _, _, _, _, section_flags, reserved1, reserved2, _ = struct.unpack_from('<IIIIIIII', c, pos+48)
                result['sections'].append({'name': section.rstrip(b'\0').decode(),
                    'segment': segment.rstrip(b'\0').decode(), 'VM_address': address, 'size': section_size,
                    'flags': section_flags, 'reserved1': reserved1, 'reserved2': reserved2})
        elif command == 0x2:
            require(length >= 24, 'symbol table command')
            symoff, symbols, stroff, strings = struct.unpack_from('<IIII', c, 8)
            result['symbol_table'] = {'file_offset': symoff, 'count': symbols,
                                      'strings_offset': stroff, 'strings_size': strings}
        elif command == 0xb:
            require(length >= 80, 'dynamic symbol table command')
            indirect, symbols = struct.unpack_from('<II', c, 56)
            result['indirect_symbol_table'] = {'file_offset': indirect, 'count': symbols}
        elif command in [0x26, 0x80000033]:
            require(length >= 16, 'linkedit data command')
            linkdata[command] = struct.unpack_from('<II', c, 8)
        elif command == 0x32:
            require(length >= 24, 'build version command')
            platform, minos, sdk = struct.unpack_from('<III', c, 8)
            result['build_versions'].append({'platform': platform, 'minimum_OS': minos, 'SDK': sdk})
        offset += length
    require(offset == size and result['UUID'] and result['install_name'] == expected_name, 'image identity')
    link = next(s for s in result['segments'] if s['name'] == '__LINKEDIT')
    starts = []
    if 0x26 in linkdata:
        fileoff, size = linkdata[0x26]
        require(link['file_offset'] <= fileoff and fileoff + size <= link['file_offset'] + link['file_size'], 'function starts extent')
        raw = cache.read(link['VM_address'] + fileoff - link['file_offset'], size)
        position, address = 0, base
        while position < len(raw):
            delta, position = uleb(raw, position)
            if not delta:
                require(not any(raw[position:]), 'nonzero function-start padding')
                break
            address += delta
            require(base <= address < base + MAX_READ and len(starts) < 1000000, 'function starts bounds')
            starts.append(address)
        result['function_starts_data_SHA256'] = hashlib.sha256(raw).hexdigest()
    if 0x80000033 in linkdata:
        fileoff, size = linkdata[0x80000033]
        require(link['file_offset'] <= fileoff and fileoff + size <= link['file_offset'] + link['file_size'], 'export trie extent')
        raw = cache.read(link['VM_address'] + fileoff - link['file_offset'], size)
        result['export_trie_SHA256'] = hashlib.sha256(raw).hexdigest()
        result['export_trie_bytes'] = size
    result['function_starts_count'] = len(starts)
    result['header_load_commands_SHA256'] = hashlib.sha256(head + data).hexdigest()
    return result, starts


def linkedit_read(cache, image, offset, size):
    link = next(s for s in image['segments'] if s['name'] == '__LINKEDIT')
    require(link['file_offset'] <= offset and offset + size <= link['file_offset'] + link['file_size'],
            'linkedit reference extent')
    return cache.read(link['VM_address'] + offset - link['file_offset'], size)


def stub_symbol(cache, image, target):
    """Return a static binding name, never claim a runtime-resolved target."""
    matches = [s for s in image['sections'] if s['flags'] & 255 == 8
               and s['VM_address'] <= target < s['VM_address'] + s['size']]
    if not matches:
        return None
    require(len(matches) == 1, 'ambiguous stub section')
    section = matches[0]
    stride = section['reserved2']
    require(stride > 0 and (target - section['VM_address']) % stride == 0, 'stub alignment')
    index = section['reserved1'] + (target - section['VM_address']) // stride
    indirect, symbols = image['indirect_symbol_table'], image['symbol_table']
    require(index < indirect['count'], 'indirect symbol index')
    symbol, = struct.unpack('<I', linkedit_read(cache, image, indirect['file_offset'] + index*4, 4))
    require(symbol < symbols['count'], 'named symbol index')
    row = linkedit_read(cache, image, symbols['file_offset'] + symbol*16, 16)
    nameoff, kind, section_number, description, value = struct.unpack('<IBBHQ', row)
    require(nameoff < symbols['strings_size'], 'symbol string index')
    text = linkedit_read(cache, image, symbols['strings_offset'] + nameoff,
                         min(4096, symbols['strings_size']-nameoff))
    return {'static_symbol': cstring(text, 0, len(text)), 'stub_VM': target,
            'symbol_index': symbol, 'nlist_type': kind, 'runtime_target_proved': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache', type=Path, required=True)
    parser.add_argument('--image', required=True)
    parser.add_argument('--expected-uuid')
    parser.add_argument('--offset', type=lambda x: int(x, 0))
    parser.add_argument('--capture-region', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    out.relative_to(ROOT / 'results')
    require(not out.exists(), 'new output directory required')
    cachepath = args.cache.resolve()
    map_path = cachepath.with_name(cachepath.name + '.map')
    mapped = image_map(map_path, args.image)
    base = mapped[0]['start']
    cache = Cache(cachepath)
    result, starts = inspect(cache, base, args.image)
    if args.expected_uuid:
        require(result['UUID'] == args.expected_uuid.lower().replace('-', ''), 'runtime/cache UUID mismatch')
    region, payload = None, None
    if args.offset is not None:
        target = base + args.offset
        index = bisect.bisect_right(starts, target) - 1
        require(index >= 0 and index+1 < len(starts), 'bounded containing function not found')
        begin, end = starts[index:index+2]
        require(begin <= target < end and end - begin <= 65536, 'bounded function range')
        payload = cache.read(begin, end-begin)
        region = {'target_VM': target, 'target_image_offset': args.offset, 'start_VM': begin, 'end_VM': end,
                  'bytes': len(payload), 'SHA256': hashlib.sha256(payload).hexdigest(),
                  'boundary_source': 'LC_FUNCTION_STARTS', 'exact_source_function_identity_proved': False}
    out.mkdir(exist_ok=False)
    inspector_source = Path(__file__).read_bytes()
    (out / 'inspector.py').write_bytes(inspector_source)
    if args.capture_region:
        require(payload is not None, 'capture requires a bounded offset')
        (out / 'function-region.private.bin').write_bytes(payload)
    dependencies = []
    for i in sorted(cache.used):
        part = dict(cache.parts[i])
        part['SHA256'] = sha(part['path'])
        dependencies.append(part)
    report = {'status': 'PASS', 'image': result, 'image_base_VM': base, 'map_ranges': mapped,
              'cache_map_SHA256': sha(map_path), 'cache_parts_read': dependencies, 'region': region,
              'runtime_UUID_matched': bool(args.expected_uuid), 'resident_code_identity_proved': False,
              'region_captured_privately': args.capture_region, 'standalone_dylib_reconstructed': False,
              'inspector_source_SHA256': hashlib.sha256(inspector_source).hexdigest(),
              'native_program_executed': False, 'system_modified': False}
    (out / 'metadata.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'status': 'PASS', 'UUID': result['UUID'], 'function_starts': len(starts),
                      'region': region, 'cache_parts_read': len(dependencies), 'executed': False}))


if __name__ == '__main__':
    main()
