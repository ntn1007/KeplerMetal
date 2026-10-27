#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare an archived video profile with current files, without repinning it.

The prior audit contains original file words and external relocation metadata;
Ghidra's relocated table is deliberately not compared with raw Mach-O bytes.
This reads files only. A matching table is not a qualification of live code.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

# Bounded parsers from the original MIT-licensed local video auditors.
def require(value, message):
    if not value:
        raise ValueError(message)

def file_bytes(data, address, count):
    require(struct.unpack_from('<II', data) == (0xfeedfacf, 0x01000007), 'thin x86_64 Mach-O')
    commands, size = struct.unpack_from('<II', data, 16)
    require(commands <= 4096 and size + 32 <= len(data), 'load commands bounded')
    offset = 32
    found = []
    for _ in range(commands):
        command, length = struct.unpack_from('<II', data, offset)
        require(length >= 8 and offset + length <= 32 + size, 'load command length')
        if command == 0x19:
            vm, _, file, extent = struct.unpack_from('<QQQQ', data, offset + 24)
            if vm <= address and address + count <= vm + extent:
                start = file + address - vm
                require(start + count <= len(data), 'file range bounded')
                found.append((start, data[start:start + count]))
        offset += length
    require(offset == 32 + size and len(found) == 1, 'unique complete file mapping')
    return found[0]


def symbols_and_external_relocations(data):
    require(len(data) >= 32 and struct.unpack_from('<II', data) ==
            (0xfeedfacf, 0x01000007), 'thin x86_64 Mach-O')
    count, extent = struct.unpack_from('<II', data, 16)
    require(count <= 4096 and 32 + extent <= len(data), 'bounded load commands')
    off = 32
    sym = dysym = None
    for _ in range(count):
        cmd, size = struct.unpack_from('<II', data, off)
        require(size >= 8 and size % 4 == 0 and off + size <= 32 + extent,
                'complete load command')
        if cmd == 2:
            require(size == 24 and sym is None, 'unique LC_SYMTAB')
            sym = struct.unpack_from('<6I', data, off)
        if cmd == 11:
            require(size == 80 and dysym is None, 'unique LC_DYSYMTAB')
            dysym = struct.unpack_from('<20I', data, off)
        off += size
    require(off == 32 + extent and sym is not None and dysym is not None,
            'complete symbol metadata')
    _, _, symoff, nsyms, stroff, strsize = sym
    require(symoff + 16 * nsyms <= len(data) and stroff + strsize <= len(data),
            'bounded symbol/string tables')
    symbols = []
    for i in range(nsyms):
        ix, typ, sect, desc, value = struct.unpack_from('<IBBHQ', data, symoff + 16 * i)
        require(ix < strsize, 'symbol string offset')
        end = data.index(b'\x00', stroff + ix, stroff + strsize)
        symbols.append(dict(name=data[stroff + ix:end].decode('utf-8'), type=typ,
                            section=sect, description=desc, value=value, index=i))
    extoff, nextrel = dysym[16:18]
    require(extoff + nextrel * 8 <= len(data), 'bounded external relocations')
    relocations = {}
    for i in range(nextrel):
        address, word = struct.unpack_from('<II', data, extoff + i * 8)
        require(not address & 0x80000000, 'non-scattered x86_64 relocation')
        symnum = word & 0xffffff
        require(symnum < len(symbols), 'external relocation symbol index')
        entry = dict(address=address, file_offset=extoff + i * 8,
                     pc_relative=(word >> 24) & 1, length_code=(word >> 25) & 3,
                     external=(word >> 27) & 1, type=word >> 28, symbol=symbols[symnum])
        relocations.setdefault(address, []).append(entry)
    return symbols, relocations


AUDIT_SHA = '609ef5dabd788833ec295222113e759dfc48e2bf73f1e3fcb286854dcd95cd66'
INVENTORY_SHA = 'ce2d2ce2e381f567ad50bd9cf77747adfada6554c9b04b06683bda88ac76243e'
PRIOR_REA_SHA = '707ed2b569d686f4e39322c80075c389e1af866f5a5d02647cf10b6fb819a58b'
LEGACY_SHA = 'c735877fe16b1495a7010c707ea355c4f312465bda4cdb0b8d99ab7f34247557'

def sha_file(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()

def compare_slots(rows, binary):
    if len(rows) != 28 or len({row['cell_address'] for row in rows}) != 28:
        raise ValueError('The archived 28-cell table is incomplete')
    _, relocs = symbols_and_external_relocations(binary)
    changes = []
    for row in rows:
        address = int(row['cell_address'], 16)
        _, word = file_bytes(binary, address, 8)
        actual = struct.unpack('<Q', word)[0]
        expected = int(row['original_word'],16)
        actual_relocations = relocs.get(address, [])
        prior = row.get('external_relocation')
        relocation_match = actual_relocations == ([prior] if prior else [])
        if actual != expected or not relocation_match:
            changes.append({'slot':row['slot'],'word_matches':actual == expected,
                            'relocation_metadata_matches':relocation_match})
    return {'slots_checked':len(rows),'slots_matching':len(rows)-len(changes),
            'slots_different':changes,'comparison':'original on-disk words and relocation metadata',
            'relocated_runtime_words_compared':False}

def compare_ranges(dossiers, binary):
    selected = [d for d in dossiers if d['bundle'] == 'GeForce-video-methods.private.json']
    if len(selected) != 1 or len(selected[0]['functions']) != 11:
        raise ValueError('Archived GeForce method dossier is incomplete')
    functions = selected[0]['functions']
    if len({f['address'] for f in functions}) != 11:
        raise ValueError('Archived function identities are not unique')
    ranges = []
    for function in functions:
        if function['binary_SHA256'] != LEGACY_SHA or not function['ranges']:
            raise ValueError('Archived function provenance is incomplete')
        for region in function['ranges']:
            start,end = int(region['start'],16),int(region['end'],16)
            if end < start or region['bytes'] != end-start+1:
                raise ValueError('Archived function range is malformed')
            offset,data = file_bytes(binary,start,region['bytes'])
            ranges.append({'function_address':function['address'],'bytes':len(data),
                'offset_matches':offset == region['file_offset'],
                'SHA256_matches':hashlib.sha256(data).hexdigest() == region['SHA256']})
    return {'functions_checked':len(functions),'ranges_checked':len(ranges),
            'bytes_checked':sum(r['bytes'] for r in ranges),
            'ranges_matching':sum(r['offset_matches'] and r['SHA256_matches'] for r in ranges),
            'differences':[r for r in ranges if not r['offset_matches'] or not r['SHA256_matches']],
            'scope':'Archived Ghidra-selected function ranges in the current on-disk file'}

def compare_function(prior_path, current_path, current_digest):
    if sha_file(prior_path) != PRIOR_REA_SHA:
        raise ValueError('Archived REA evidence changed')
    prior_bundle = json.loads(Path(prior_path).read_text())
    candidates = [r for r in prior_bundle['records'] if r['operation'] == 'analyze_function'
                  and r['normalized_result']['procedure']['address'] == '0x68352']
    if len(candidates) != 1:
        raise ValueError('Archived function evidence is ambiguous')
    prior, current = candidates[0], json.loads(Path(current_path).read_text())
    if (prior['subject']['digest']['sha256'] != LEGACY_SHA or
        current['subject']['digest']['sha256'] != current_digest or
        prior['operation'] != 'analyze_function' or current['operation'] != 'analyze_function' or
        prior['analysis_profile']['digest'] != current['analysis_profile']['digest'] or
        prior['provider'] != current['provider'] or
        current['normalized_result']['procedure']['address'] != '0x68352'):
        raise ValueError('Function identity, provider or analysis profile differs')
    a,b = prior['normalized_result'],current['normalized_result']
    return {'address':'0x68352','prior_evidence_id':prior['evidence_id'],
            'current_evidence_id':current['evidence_id'],
            'prior_evidence_SHA256':PRIOR_REA_SHA,'current_evidence_SHA256':sha_file(current_path),
            'body_ranges_match':a['procedure']['body'] == b['procedure']['body'],
            'assembly_match':a['assembly'] == b['assembly'],
            'pseudocode_match':a['pseudocode'] == b['pseudocode'],
            'outgoing_references_match':a['outgoing_references'] == b['outgoing_references'],
            'scope':'Decompiler representation of one function, not complete binary bytes or live execution'}

def compare(inventory_path, audit_path, geforce_path, prior_rea=None, current_rea=None):
    if sha_file(inventory_path) != INVENTORY_SHA or sha_file(audit_path) != AUDIT_SHA:
        raise ValueError('Historical evidence hash mismatch; do not silently repin')
    inventory = json.loads(Path(inventory_path).read_text())['system_before']
    audit = json.loads(Path(audit_path).read_text())
    if len(inventory) != 83 or audit['status'] != 'PASS':
        raise ValueError('Historical inventory/audit is incomplete')
    if audit['binary_pins'].get(str(geforce_path)) != LEGACY_SHA:
        raise ValueError('Historical GeForce path or identity mismatch')
    changes = []
    for row in inventory:
        path = Path(row['path'])
        try:
            current = sha_file(path)
        except (FileNotFoundError, PermissionError, IsADirectoryError):
            current = None
        if current != row['SHA256']:
            changes.append({'path':str(path),'prior_SHA256':row['SHA256'],
                            'current_SHA256':current,'readable':current is not None})
    raw = Path(geforce_path).read_bytes()
    current = hashlib.sha256(raw).hexdigest()
    table = compare_slots(audit['method_slots'],raw)
    ranges = compare_ranges(audit['static_dossiers'],raw)
    if bool(prior_rea) != bool(current_rea):
        raise ValueError('Both REA evidence files are required for function comparison')
    function = compare_function(prior_rea,current_rea,current) if prior_rea else None
    return {'status':'DRIFT_DETECTED' if changes else 'INVENTORY_MATCH',
            'prior_inventory_SHA256':INVENTORY_SHA,'prior_command_audit_SHA256':AUDIT_SHA,
            'inventory_count':len(inventory),'changed_count':len(changes),'changes':changes,
            'prior_GeForce_SHA256':LEGACY_SHA,'current_GeForce_SHA256':current,
            'table_comparison':table,'function_ranges':ranges,'function_comparison':function,'current_live_code_compared':False,
            'current_video_profile_qualified':False,'GPU_or_RM_execution':False,
            'system_modified':False,
            'limits':['Archived file snapshots compared to current paths; not a live kernel measurement.',
                      'A matching 28-cell table does not establish identical method bodies, capability or safety.',
                      'Changes are not attributed to a cause; the old profile remains blocked.']}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for n in ('inventory','audit','geforce','out'):
        p.add_argument('--'+n, type=Path, required=True)
    p.add_argument('--prior-rea',type=Path)
    p.add_argument('--current-rea',type=Path)
    a = p.parse_args()
    if a.out.exists() or not a.out.parent.is_dir():
        raise ValueError('Use a fresh result path in an existing output directory')
    result = compare(a.inventory.resolve(),a.audit.resolve(),a.geforce.resolve(),a.prior_rea,a.current_rea)
    with a.out.open('x') as f:
        json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({'status':result['status'],'changed':result['changed_count'],
        'slots_matching':result['table_comparison']['slots_matching'],
        'function_ranges_matching':result['function_ranges']['ranges_matching'],
        'profile_qualified':False,'GPU_or_RM_execution':False}))

if __name__ == '__main__': main()
