#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check pinned, offline evidence on video context ownership; never opens IOKit."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

from compare_video_profile import file_bytes, symbols_and_external_relocations
from video_method_contract import IO_SHA, GE_SHA, symbol_one

# These are captures from the REA MCP response, not redistributed driver code.
EVIDENCE = {
 '0x83b4': ('link', 'ec73d8735a3fd96bad36145b129979ee5cb68387a3335200c1309c716d548fbd', 'ev_bee5bc6856791f275d991d8a50ebe05e56f2911012c7e6b1aa5b7f1cd3f778f1', 591, ['0x845d: CMP R15, qword ptr [R14 + 0xf8]', '0x849c: CMP RAX, qword ptr [RBX + 0x578]', '0x8512: CMP qword ptr [RBX + 0x5a0], 0x0', '0x8558: MOV qword ptr [RBX + 0x5a0], RDI', '0x85bc: CALL qword ptr [RAX + 0x5c0]']),
 '0x2b056': ('link', 'e01bde5c00abb9cd4ac1cb4fe3a301d8aecaf691415c375c7cc666fed1df9d3f', 'ev_0184de253bb8a43a6e8088d4df57af2309ff685771640f33ab5bb24a54977511', 111, ['0x2b08e: MOV qword ptr [RBX + 0xe0], R15']),
 '0x2b0c6': ('link', '3bec884762f8b954bac8084e3c8b91073cd87d9af73fadfbcfacdf84971090ae', 'ev_ddc01ec0bd4e8d6222ee6ca89c252bcc7175bbbb25a9b43b1396ea7c32861818', 234, ['0x2b0fd: MOV qword ptr [RBX + 0xf8], RAX']),
 '0x2b7b2': ('link', 'ca42e2cf179b365e198e3a54c20dd102e7f897b62c7af311282428ec35fe75e7', 'ev_24e6e61d0c50bb5d7df35138bb51a27873eb08c5a62d2fee2cda82411cb49815', 84, ['0x2b7f9: CALL qword ptr [RAX + 0x600]']),
 '0x7eea': ('ownership', 'd5e663b382ae042e5b9b67ff13eb7b7379897d1664a8ec7dee110395fb6622bb', 'ev_1884adaec23bec032e598965592d81a25cca1306b656c129459d8aa1abb1399a', 631, ['0x8064: CALL 0x00008162', '0x8075: CALL 0x0002aa8c', '0x8087: MOV qword ptr [RBX + 0x5a0], 0x0']),
 '0x8162': ('ownership', '29b3079b9d69316f3ace9d4425a6a67374235c3e98a0e65fc3c3c540ed18d2a1', 'ev_ee8511cd806b2b37e4c767451d79fcdafd4a2f155343fc044586ac2ae0bcfe16', 545, ['0x823e: CALL 0x00021a10', '0x82ee: CALL 0x00021a10']),
 '0x3a062': ('parent', 'ab4a3cb9495523fc909c5383540dc0e4fc5e03ec5192947fdf2a2de5f07cf8b0', 'ev_5099c7c1b4081816814754d254a6e2d5bcf00e748a1d52d81a8060b1097379c0', 72, ['0x3a096: LEA RAX, [0x6d760]', '0x3a0a4: JMP qword ptr [RAX + 0x9f8]']),
 '0x7880': ('parent', 'dae6ad161f934a828bae0e17fcc1934fc16506718546d678638722ca9bf5c384', 'ev_95e9b16533ee7ba34ba58b41e72f5a13b4ea5a707964423aae085f5babba6b86', 211, ['0x78dd: CALL qword ptr [RAX + 0x9e8]']),
 '0x7954': ('ownership', 'f3d4cb6326c23e76e3df9b1fcffce30ea0b788dad95de6b32ec46049195c90d0', 'ev_0491c9b5a4da4b3c854f4d073c7e0882688224d044dabb1309e2eb11e22b4541', 51, ['0x7966: CALL qword ptr [RAX + 0x600]', '0x797d: CALL qword ptr [RAX + 0x678]']),
}

NVIDIA_STOP = ('nvidia', 'cefd15abcac4a8328985ddaaefca57b65080626ad7cca026db22919c15ed2fcf', 'ev_b970248367bcb334bc50119cc8a5cc230a6c2d77a8fc0ddca11a1867f50a1230', 18, ['0x68344: MOV RAX, qword ptr [0x0007b1a0]', '0x6834c: JMP qword ptr [RAX + 0x9f8]'])

SLOTS = {
 0x5c0: '__ZN15IOAccelContext25startEP9IOService',
 0x5c8: '__ZN15IOAccelContext24stopEP9IOService',
 0x600: '__ZN9IOService9terminateEj',
 0x678: '__ZN9IOService6detachEPS_',
 0x8f0: '__ZN15IOAccelContext211clientCloseEv',
 0x918: '__ZN15IOAccelContext213connectClientEP12IOUserClient',
}

def digest(data):
    return hashlib.sha256(data).hexdigest()

def check_evidence(path, address, spec, subject_sha=IO_SHA):
    _, expected_hash, eid, size, anchors = spec
    raw = path.read_bytes()
    if digest(raw) != expected_hash:
        raise ValueError('REA capture hash differs: ' + address)
    evidence = json.loads(raw)['result']['structuredContent']
    normalized = evidence['normalized_result']
    if (evidence['operation'] != 'analyze_function' or
        evidence['subject']['digest']['sha256'] != subject_sha or
        evidence['evidence_id'] != eid or
        evidence['provider'] != {'id':'ghidra', 'name':'Ghidra', 'version':'12.1.4'} or
        evidence['analysis_profile']['digest'] != 'c027fac311b23874c52441ed55610273dff33987b0370a0589c90be8f6d72b7a' or
        normalized['procedure']['address'] != address or
        normalized['procedure']['body']['total_bytes'] != size or
        not all(x in normalized['assembly'] for x in anchors)):
        raise ValueError('REA identity or instruction anchors differ: ' + address)
    return {'address':address, 'capture_SHA256':expected_hash, 'evidence_id':eid, 'bytes':size}

def check_profile(io_path, ge_path):
    io, ge = io_path.read_bytes(), ge_path.read_bytes()
    if digest(io) != IO_SHA or digest(ge) != GE_SHA:
        raise ValueError('Installed binary profile differs')
    symbols, relocs = symbols_and_external_relocations(ge)
    if symbol_one(symbols, '__ZTV14nvVideoContext')['value'] != 0x90fe8:
        raise ValueError('nvVideoContext vtable differs')
    slots = []
    for slot, name in SLOTS.items():
        address = 0x90ff8 + slot
        rows = relocs.get(address, [])
        if (len(rows) != 1 or rows[0]['symbol']['name'] != name or
            (rows[0]['external'],rows[0]['length_code'],rows[0]['type'],rows[0]['pc_relative']) != (1,3,0,0) or
            file_bytes(ge,address,8)[1] != b'\0'*8):
            raise ValueError('Unexpected vtable relocation at ' + hex(address))
        slots.append({'slot':hex(slot),'external_symbol':name})
    address = 0x90ff8 + 0x9e8
    target = struct.unpack('<Q', file_bytes(ge,address,8)[1])[0]
    if relocs.get(address) or target != 0x68340 or symbol_one(symbols, '__ZN14nvVideoContext11contextStopEv')['value'] != target:
        raise ValueError('Unexpected NVIDIA contextStop override')
    parent = relocs.get(0x7b1a0, [])
    if (len(parent) != 1 or parent[0]['symbol']['name'] != '__ZTV20IOAccelVideoContext2' or
        (parent[0]['external'],parent[0]['length_code'],parent[0]['type'],parent[0]['pc_relative']) != (1,3,0,0) or
        file_bytes(ge,0x7b1a0,8)[1] != b'\0'*8):
        raise ValueError('Unexpected parent video vtable relocation')
    iosymbols, iorelocs = symbols_and_external_relocations(io)
    parent_table = symbol_one(iosymbols, '__ZTV20IOAccelVideoContext2')['value']
    cell = parent_table + 0x9f8
    target = struct.unpack('<Q', file_bytes(io,cell,8)[1])[0]
    if (parent_table != 0x7ac60 or iorelocs.get(cell) or target != 0x3a062 or
        symbol_one(iosymbols, '__ZN20IOAccelVideoContext211contextStopEv')['value'] != target):
        raise ValueError('Unexpected parent contextStop slot')
    base_table = symbol_one(iosymbols, '__ZTV15IOAccelContext2')['value']
    cell = base_table + 0x9f8
    target = struct.unpack('<Q', file_bytes(io,cell,8)[1])[0]
    if (base_table != 0x6d760 or iorelocs.get(cell) or target != 0x7eea or
        symbol_one(iosymbols, '__ZN15IOAccelContext211contextStopEv')['value'] != target):
        raise ValueError('Unexpected base contextStop slot')
    return slots

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for arg in ('ioaccel','geforce','link','ownership','nvidia','parent','out'):
        p.add_argument('--'+arg, type=Path, required=True)
    a=p.parse_args()
    if a.out.exists() or not a.out.parent.is_dir():
        raise ValueError('Fresh output directory required')
    slots=check_profile(a.ioaccel,a.geforce)
    captures=[check_evidence(getattr(a,spec[0])/(address+'.private.json'),address,spec) for address,spec in EVIDENCE.items()]
    captures.append(check_evidence(a.nvidia/'0x68340.private.json','0x68340',NVIDIA_STOP,GE_SHA))
    result={'status':'PASS','scope':'static pinned binaries and REA captures only','IOAccelerator_SHA256':IO_SHA,'GeForce_SHA256':GE_SHA,'vtable_external_relocations':slots,'nvVideoContext_contextStop_override':'0x68340','parent_vtable_target_on_disk':'0x3a062','base_vtable_target_on_disk':'0x7eea','function_evidence':captures,'live_connections':0,'hardware_video_execution_proved':False,'cleanup_after_connect_observed':False}
    a.out.mkdir()
    (a.out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':'PASS','functions':len(captures),'live_connections':0,'hardware_video_execution_proved':False}))

if __name__ == '__main__':
    main()
