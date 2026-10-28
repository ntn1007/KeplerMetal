#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare pinned RM control paths offline; never send a driver request."""
import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'tools'))
from compare_video_profile import file_bytes, symbols_and_external_relocations

NVDA = '36396eaecd68ddbb0482f019f38ce55d01b10379ca829da7f19b3bd8f3e26808'
CUDA = 'fb646845ca1f885f71cc5394c059a57aef36fdf32b1029ad891c372090c9b9f4'
OLD_REA = 'cce234fd43bcaa8851b92ffc8d3346f066488e0e730d83ff88a9e2156d48da89'
NEW_REA = '7251033d303a0ad331bbd6acee7de0c0342b594e4a0948e510af20a7d8f2d0a0'
CUDA_BODY = 'cbdf65c906768b631cb86dfe7fc528de259990255444b5e1d14ecbd785f8fbbb'
FUNCTIONS = {
    0x32e88: (15, 'a0f00af581c87af3d3d57acdf4ffcbe865e39d7ad99f307a2e2de5ef87e44e7e', 'ev_b692561b06480a3fa191e15161cda5adfafeb629859026f454a768839ed65626'),
    0x32238: (154, '9d104a9c7e283fc19dfa781d5f800293f5630831c6fbd71f1cad7c370cd8d5dc', 'ev_0006c29988aad5623d77f7df46d92b30a83350e5084b164eca67e7dc9016c78c'),
    0x441fb: (26, '932e9954e472e99df7705958e7763adfe35c75d135ce2da6efe7715267bba871', 'ev_c7d4db27b24021a952366b383b10bf2417c00626d549463e103440c8e39cce55'),
    0x44215: (1054, '80cdfcce196fe7c66dffb76cfb3bcb2c7ef7c7b94d51dff8cd9e1aa1a32aa554', 'ev_bce34254a84acd06a26459fe7cdfe1deccb49f898f8f21d1d8c472e5fdf755d8'),
    0x724f0: (143, 'c1950a138812bf2c45bf2e7c7a8da2972c2d5463bac0fc41ce9743c7df4c7309', 'ev_a1fe45e17b5c646b45f671be8af58d060a886c6bfd9aabc101e78e38df6ddd20'),
    0x708d0: (5200, 'ede714b30b45d91e2d0d48bbba198780cd0132e100756a959606c5a0d3f42cfc', 'ev_c4a0fc1ca731c6e7c45a9ecb98bc1107e4144310fa1e2b1a2fc24bfa0ddbe479'),
}

def need(ok, message):
    if not ok:
        raise ValueError(message)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def direct(data, address, target, op=0xe8):
    _, b = file_bytes(data, address, 5)
    need(b[0] == op and address + 5 + struct.unpack_from('<i', b, 1)[0] == target,
         'branch ' + hex(address))

def inspect(nvda, cuda, old, new):
    need(sha(nvda) == NVDA and sha(cuda) == CUDA, 'vendor input identity')
    need(sha(old) == OLD_REA and sha(new) == NEW_REA, 'REA evidence identity')
    records = {r['evidence_id']: r for bundle in (old, new)
               for r in json.loads(bundle)['records']}
    functions = {}
    for address, (size, digest, evidence) in FUNCTIONS.items():
        offset, code = file_bytes(nvda, address, size)
        need(sha(code) == digest, 'function ' + hex(address))
        r = records[evidence]
        p = r['normalized_result']['procedure']
        need(r['subject']['digest']['sha256'] == NVDA and p['address'] == hex(address)
             and p['body']['total_bytes'] == size and p['body']['contains_entry']
             and not p['body']['non_contiguous'], 'REA function ' + hex(address))
        functions[hex(address)] = {'bytes': size, 'file_offset': offset,
                                   'sha256': digest, 'evidence_id': evidence}
    dispatcher = records[FUNCTIONS[0x708d0][2]]['normalized_result']
    mappings = [m for table in dispatcher['native_api']['jump_tables']
                for m in table['mappings'] if m['case_value'] == 0x702a]
    need(len(mappings) == 1 and mappings[0]['target_address'] == '0x70b7b', 'dispatch case')
    # Independently check the relative jump-table cell and selected call edges.
    _, cell = file_bytes(nvda, 0x71d2c, 4)
    need(0x71d20 + struct.unpack('<i', cell)[0] == 0x70b7b, 'dispatch table')
    for source, target, op in [(0x70be5, 0x32e88, 0xe8), (0x32e92, 0x32238, 0xe9),
                               (0x322b1, 0x441fb, 0xe8), (0x4420a, 0x44215, 0xe8),
                               (0x72564, 0x708d0, 0xe8)]:
        direct(nvda, source, target, op)
    _, code = file_bytes(cuda, 0x22bfc4, 174)
    need(sha(code) == CUDA_BODY, 'CUDA original window')
    direct(cuda, 0x22c058, 0x22d524)
    syms, _ = symbols_and_external_relocations(nvda)
    need(any(s['value'] == 0x724f0 and s['name'] == '_NvRmControl' for s in syms),
         'NvRmControl symbol')
    return {'status': 'PASS_STATIC_CONTROL_PATH', 'nvda_sha256': NVDA, 'cuda_sha256': CUDA,
            'old_rea_sha256': OLD_REA, 'new_rea_sha256': NEW_REA, 'functions': functions,
            'cuda_window_sha256': CUDA_BODY, 'cuda_window_start': '0x22bfc4',
            'dispatch_case': '0x702a', 'dispatch_target': '0x70b7b',
            'scope': 'Static structure and selected edges only; nested pointers, live transport, ownership and class-list retrieval are unqualified.',
            'private_RM_calls': 0, 'GPU_dispatches': 0, 'system_modified': False}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for flag in ('nvda', 'cuda', 'old-rea', 'new-rea', 'out'):
        p.add_argument('--' + flag, type=Path, required=True)
    a = p.parse_args()
    need(a.out.parent.is_dir() and not a.out.exists(), 'fresh output required')
    result = inspect(a.nvda.read_bytes(), a.cuda.read_bytes(), a.old_rea.read_bytes(), a.new_rea.read_bytes())
    with a.out.open('x') as f:
        json.dump(result, f, indent=2, sort_keys=True)
        f.write('\n')
    print(json.dumps(result, sort_keys=True))

if __name__ == '__main__':
    main()
