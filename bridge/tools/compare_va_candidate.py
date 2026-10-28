#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare bounded x86_64 Mach-O exported factory ranges, without loading them.

This is static evidence only. A non-stub body is not a hardware, ABI, or
operating-system compatibility result. No vendor bytes are emitted.
"""
import argparse
import bisect
import collections
import hashlib
import json
import re
import struct
import subprocess
from pathlib import Path

CPU_X86_64 = 0x01000007
LC_SEGMENT_64 = 0x19
LC_SYMTAB = 0x2
LC_FUNCTION_STARTS = 0x26
LC_UUID = 0x1b
STUB_SHA = '56ab2f750b92826bbc9b12d9878950be8e7783a12315c2efcdcd169726fe8eb4'


def require(value, message):
    if not value:
        raise ValueError(message)


def bounded(data, offset, size):
    require(offset >= 0 and size >= 0 and offset <= len(data) and size <= len(data) - offset, 'range outside file')
    return data[offset:offset + size]


def thin_x86(data):
    require(len(data) >= 8, 'truncated file')
    if data[:4] == b'\xca\xfe\xba\xbe':
        count = struct.unpack_from('>I', data, 4)[0]
        require(0 < count <= 64 and 8 + 20 * count <= len(data), 'invalid FAT table')
        entries = []
        for i in range(count):
            cpu, _, offset, size, _ = struct.unpack_from('>IIIII', data, 8 + 20 * i)
            bounded(data, offset, size)
            if cpu == CPU_X86_64:
                entries.append((offset, size))
        require(len(entries) == 1, 'x86_64 slice missing or ambiguous')
        offset, size = entries[0]
        data = bounded(data, offset, size)
    require(len(data) >= 32 and struct.unpack_from('<II', data) == (0xfeedfacf, CPU_X86_64), 'not x86_64 Mach-O')
    return data


def uleb_starts(data, start, size, base):
    end = start + size
    bounded(data, start, size)
    out = []
    while start < end:
        delta = shift = 0
        while True:
            require(start < end and shift < 64, 'truncated or overflowing function-start entry')
            b = data[start]; start += 1
            delta |= (b & 0x7f) << shift
            shift += 7
            if not b & 0x80:
                break
        if not delta:
            return out
        base += delta
        require(base <= 0xffffffffffffffff, 'function address overflow')
        out.append(base)
    raise ValueError('function-start table lacks terminator')


def inspect_bytes(blob, symbol):
    data = thin_x86(blob)
    count, size = struct.unpack_from('<II', data, 16)
    require(count <= 4096 and 32 + size <= len(data), 'load commands outside file')
    cursor, end = 32, 32 + size
    text = symtab = starts = uuid = None
    for _ in range(count):
        require(cursor + 8 <= end, 'truncated load command')
        command, length = struct.unpack_from('<II', data, cursor)
        require(length >= 8 and length % 4 == 0 and cursor + length <= end, 'invalid load command')
        if command == LC_SEGMENT_64 and length >= 72 and data[cursor + 8:cursor + 24].split(b'\0', 1)[0] == b'__TEXT':
            require(text is None, 'duplicate __TEXT')
            text = struct.unpack_from('<QQQQ', data, cursor + 24)
        elif command == LC_SYMTAB:
            require(length == 24 and symtab is None, 'invalid symbol command')
            symtab = struct.unpack_from('<IIII', data, cursor + 8)
        elif command == LC_FUNCTION_STARTS:
            require(length == 16 and starts is None, 'invalid function-start command')
            starts = struct.unpack_from('<II', data, cursor + 8)
        elif command == LC_UUID:
            require(length == 24 and uuid is None, 'invalid UUID command')
            uuid = data[cursor + 8:cursor + 24].hex()
        cursor += length
    require(cursor == end and text and symtab and starts and uuid, 'incomplete Mach-O metadata')
    vm, vm_size, file_offset, file_size = text
    bounded(data, file_offset, file_size)
    require(file_size <= vm_size, '__TEXT size mismatch')
    symoff, nsym, stroff, strsize = symtab
    require(nsym <= 2_000_000, 'symbol count exceeds bound')
    bounded(data, symoff, nsym * 16); strings = bounded(data, stroff, strsize)
    matches = []
    for i in range(nsym):
        index, typ, _, _, address = struct.unpack_from('<IBBHQ', data, symoff + 16 * i)
        require(index < len(strings), 'symbol name outside table')
        finish = strings.find(b'\0', index)
        require(finish >= 0, 'unterminated symbol name')
        if strings[index:finish] == symbol.encode('ascii') and typ & 0x0e == 0x0e and typ & 1:
            matches.append(address)
    require(len(matches) == 1, 'export absent or ambiguous')
    target = matches[0]
    functions = uleb_starts(data, *starts, vm)
    require(target in functions, 'export not a recorded function start')
    i = functions.index(target)
    require(i + 1 < len(functions), 'next function boundary unavailable')
    next_start = functions[i + 1]
    require(vm <= target < next_start <= vm + file_size and next_start - target <= 65536, 'function outside __TEXT or too large')
    raw = bounded(data, file_offset + target - vm, next_start - target)
    return {'architecture': 'x86_64', 'UUID': uuid, 'file_SHA256': hashlib.sha256(blob).hexdigest(),
            'slice_SHA256': hashlib.sha256(data).hexdigest(), 'symbol': symbol,
            'function_start': target, 'next_function_start': next_start,
            'function_bytes': len(raw), 'function_SHA256': hashlib.sha256(raw).hexdigest(),
            'exact_known_return_14_stub': hashlib.sha256(raw).hexdigest() == STUB_SHA}


def disassembly(path, row):
    command = ['xcrun', 'otool', '-arch', 'x86_64', '-tvV', '-p', row['symbol'], str(path)]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=True)
    instructions = []
    relevant = []
    for line in result.stdout.splitlines():
        match = re.match(r'^([0-9a-fA-F]{16})\s+(\S+)', line)
        if match and row['function_start'] <= int(match.group(1), 16) < row['next_function_start']:
            instructions.append((int(match.group(1), 16), match.group(2)))
            relevant.append(line)
    require(instructions and instructions[0][0] == row['function_start'], 'disassembly did not begin at pinned export')
    zero_296_sites = []
    for index, line in enumerate(relevant):
        if 'symbol stub for: ___bzero' in line and any(re.search(r'\bmovl\s+\$0x128,\s*%esi(?:\s|$)', x) for x in relevant[max(0, index - 4):index]):
            zero_296_sites.append(int(line.split()[0], 16))
    return {'instruction_count': len(instructions),
            'call_instructions': sum(m.startswith('call') for _, m in instructions),
            'conditional_jumps': sum(m.startswith('j') and not m.startswith('jmp') for _, m in instructions),
            'return_instructions': sum(m.startswith('ret') for _, m in instructions),
            'bzero_with_296_byte_immediate_sites': zero_296_sites,
            'tool': 'xcrun otool x86_64', 'machine_code_published': False}


def find_direct_path(graph, start, destinations):
    queue = collections.deque([(start, [])])
    visited = {start}
    while queue:
        function, path = queue.popleft()
        if function in destinations:
            return path, function
        for target, callsite in graph.get(function, []):
            if target not in visited:
                visited.add(target)
                queue.append((target, path + [(function, callsite, target)]))
    return None


def kernel_imports(path, entry):
    # Counts direct calls to named symbol stubs only. This does not inventory
    # indirect calls or identify the concrete IOService received by a caller.
    names = ('IOServiceOpen', 'IOServiceClose', 'IOConnectCallMethod',
             'IOConnectCallScalarMethod', 'IOConnectCallStructMethod',
             'IOConnectMapMemory64', 'IOSurfaceCreate')
    result = subprocess.run(['xcrun', 'otool', '-arch', 'x86_64', '-tvV', str(path)],
                            capture_output=True, text=True, timeout=30, check=True)
    lines = result.stdout.splitlines()
    # LC_FUNCTION_STARTS was already validated by inspect_bytes. Decode it
    # again to assign each direct callsite to its containing function.
    data = thin_x86(Path(path).read_bytes())
    count = struct.unpack_from('<I', data, 16)[0]
    offset, base, table = 32, None, None
    for _ in range(count):
        command, length = struct.unpack_from('<II', data, offset)
        if command == LC_SEGMENT_64 and data[offset + 8:offset + 24].split(b'\0', 1)[0] == b'__TEXT':
            base = struct.unpack_from('<Q', data, offset + 24)[0]
        elif command == LC_FUNCTION_STARTS:
            table = struct.unpack_from('<II', data, offset + 8)
        offset += length
    require(base is not None and table is not None, 'function boundaries unavailable')
    starts = uleb_starts(data, *table, base)
    start_set = set(starts)
    graph, open_functions = {}, {}
    sites = {name: [] for name in names}
    type_three = []
    scalar_immediates = []
    for index, line in enumerate(lines):
        direct = re.match(r'^([0-9a-fA-F]{16})\s+callq?\s+0x([0-9a-fA-F]+)', line)
        if direct:
            address, target = int(direct.group(1), 16), int(direct.group(2), 16)
            position = bisect.bisect_right(starts, address) - 1
            if position >= 0 and target in start_set:
                graph.setdefault(starts[position], []).append((target, address))
        insn = re.match(r'^([0-9a-fA-F]{16})\s+callq?\s+.*symbol stub for: _(\w+)\s*$', line)
        if not insn or insn.group(2) not in sites:
            continue
        name, address = insn.group(2), int(insn.group(1), 16)
        sites[name].append(address)
        if name == 'IOConnectCallScalarMethod':
            # SysV x86_64 passes the selector in ESI. Only nearby constant
            # assignments are reported, not dataflow-complete proof.
            nearby = lines[max(0, index - 8):index]
            matches = [re.search(r'\bmovl\s+\$0x([0-9a-fA-F]+),\s*%esi(?:\s|$)', item) for item in nearby]
            values = [int(match.group(1), 16) for match in matches if match]
            if len(values) == 1:
                scalar_immediates.append({'callsite': address, 'nearby_ESI_immediate': values[0]})
        if name == 'IOServiceOpen':
            position = bisect.bisect_right(starts, address) - 1
            if position >= 0:
                open_functions.setdefault(starts[position], []).append(address)
            nearby = lines[max(0, index - 8):index]
            if any(re.search(r'\bmovl\s+\$0x3,\s*%edx(?:\s|$)', item) for item in nearby):
                type_three.append(address)
    path_result = find_direct_path(graph, entry, set(open_functions))
    direct_path = None
    if path_result is not None:
        edges, function = path_result
        direct_path = {'edges': [{'caller_function': a, 'callsite': b, 'callee_function': c} for a, b, c in edges],
                       'open_function': function, 'open_callsites': open_functions[function]}
    return {'direct_named_stub_calls': sites, 'IOServiceOpen_type_3_immediate_sites': type_three,
            'scalar_call_nearby_selector_candidates': scalar_immediates,
            'static_direct_path_from_export_to_open': direct_path,
            'caller_service_identity_proved': False, 'selector_abi_compatibility_proved': False,
            'indirect_calls_inventoried': False}


def compare(reference, candidate):
    rows = []
    for label, path in [('installed', reference), ('candidate', candidate)]:
        row = inspect_bytes(Path(path).read_bytes(), '_AVD_CreateAVDAccelerator')
        row['label'] = label
        row['disassembly'] = disassembly(path, row)
        row['kernel_imports'] = kernel_imports(path, row['function_start'])
        rows.append(row)
    return {'status': 'STATIC_COMPARISON', 'images': rows,
            'files_loaded_or_executed': False, 'compatibility_with_GK104_proved': False,
            'macOS_compatibility_proved': False, 'hardware_video_execution_proved': False,
            'system_modified': False, 'limits': ['Function boundaries come from each image LC_FUNCTION_STARTS.',
                'Instruction counts do not establish correctness, GPU generation, calling ABI or video decoding.',
                'The installed and candidate files have different SHA-256 and must not be silently substituted.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installed', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(compare(args.installed, args.candidate), indent=2))
