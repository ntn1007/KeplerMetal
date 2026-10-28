#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the on-disk NVIDIA device allocation path; never allocate an RM object."""
import argparse
import hashlib
import json
import re
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / 'tools'))
from compare_video_profile import file_bytes, symbols_and_external_relocations

G = '44f131a958d48afd6ab675a851330c37506557c9d499484170c886c3731bdbb3'
N = '36396eaecd68ddbb0482f019f38ce55d01b10379ca829da7f19b3bd8f3e26808'
C = 'fb646845ca1f885f71cc5394c059a57aef36fdf32b1029ad891c372090c9b9f4'
REA = 'a00ae2450a3c4df49b6a1d12561f06653ba4aac53de8067ce075c6b4826e3931'
OLD = 'cce234fd43bcaa8851b92ffc8d3346f066488e0e730d83ff88a9e2156d48da89'
HEADER = '29d20eb01fdf6667a49f119380b10e883f2a841dc7cd335516f9cc43f6b05ad3'
FUNCTIONS = {
  0x6a19c: (84, 'ead138ffb2934887b2c32ff5b925a2cfc77f5303457182a7bc2771b5b393901e', 'ev_1336587b14c65e51a0261227e31d64020e4528c27788a01cf04e076a1afbdc83'),
  0x6a222: (223, 'bb7a1dbdd4853d0897b887f8ad9e543a51153b200d16948099da29b0af832dbb', 'ev_5a1e5875b8c9a5d5469e8ec930c63a3d782ab2ef4a23de66c10710eccf549590'),
  0x924c: (399, 'c5d9476a8ff70214378a87e628b3e77111861e92d9e2b130561c49ca2621cfbf', 'ev_bfc8e5163b4dbfccf20ef774b911fad08635cf00b501d1c331aa4619ae6c9b45'),
  0x69b5a: (1436, 'f802659d6a49ff68c606dc19c4464d138fa9160c2c6a979be8604024dcf5e07f', 'ev_107e366d75cf7b64500f1b38c954deab4c20ceb653844f10270e253a316d35a0'),
}

def sha(data): return hashlib.sha256(data).hexdigest()
def need(ok, reason):
    if not ok: raise ValueError(reason)

def header_declaration(text):
    need(re.search(r'#define\s+NV01_DEVICE_0\s+\(0x00000080\)', text), 'NVIDIA class')
    match = re.search(r'typedef struct\s*\{\s*NvU32\s+deviceId;\s*NvHandle\s+hClientShare;\s*'
                      r'NvHandle\s+hTargetClient;\s*NvHandle\s+hTargetDevice;\s*NvV32\s+flags;\s*'
                      r'NvU64\s+vaSpaceSize NV_ALIGN_BYTES\(8\);\s*NvU64\s+vaStartInternal NV_ALIGN_BYTES\(8\);\s*'
                      r'NvU64\s+vaLimitInternal NV_ALIGN_BYTES\(8\);\s*NvV32\s+vaMode;\s*'
                      r'\}\s*NV0080_ALLOC_PARAMETERS;', text)
    need(match is not None, 'NVIDIA allocation declaration')
    return match.group(0)

def layout(header, directory):
    decl = header_declaration(header.decode())
    fields = ['deviceId', 'hClientShare', 'hTargetClient', 'hTargetDevice', 'flags',
              'vaSpaceSize', 'vaStartInternal', 'vaLimitInternal', 'vaMode']
    offsets = [0, 4, 8, 12, 16, 24, 32, 40, 48]
    src = ('#include <stdint.h>\n#include <stddef.h>\ntypedef uint32_t NvU32;\n'
           'typedef uint32_t NvHandle;\ntypedef uint32_t NvV32;\ntypedef uint64_t NvU64;\n'
           '#define NV_ALIGN_BYTES(n) __attribute__((aligned(n)))\n' + decl + '\n' +
           '_Static_assert(sizeof(NV0080_ALLOC_PARAMETERS)==56,"size");\n' +
           ''.join('_Static_assert(offsetof(NV0080_ALLOC_PARAMETERS,%s)==%d,"offset");\n' % x
                   for x in zip(fields, offsets)) + 'int main(void){return 0;}\n')
    with tempfile.TemporaryDirectory(prefix='rm-device-layout-', dir=directory) as tmp:
        p, exe = Path(tmp) / 'layout.c', Path(tmp) / 'layout'
        p.write_text(src)
        subprocess.run(['xcrun', 'clang', '-arch', 'x86_64', '-std=c11', '-Wall', '-Werror',
                        str(p), '-o', str(exe)], check=True, capture_output=True, timeout=30)
        subprocess.run([str(exe)], check=True, capture_output=True, timeout=10)
    return dict(size=56, offsets=dict(zip(fields, offsets)), types='modeled fixed-width NVIDIA types',
                cpu_only=True)

def inspect(geforce, nvda, cuda, bundle, old, header):
    need([sha(x) for x in (geforce, nvda, cuda, bundle, old, header)] ==
         [G, N, C, REA, OLD, HEADER], 'input identities')
    records = {r['evidence_id']: r for b in (bundle, old) for r in json.loads(b)['records']}
    out = {}
    for a, (size, digest, eid) in FUNCTIONS.items():
        offset, b = file_bytes(geforce, a, size)
        p = records[eid]['normalized_result']['procedure']
        need(sha(b) == digest and records[eid]['subject']['digest']['sha256'] == G and
             p['address'] == hex(a) and p['body']['total_bytes'] == size, 'GeForce body')
        out[hex(a)] = {'sha256': digest, 'bytes': size, 'file_offset': offset, 'evidence_id': eid}
    _, b = file_bytes(nvda, 0x42614, 3239)
    need(sha(b) == 'fb840d98839edd58659f426b419ac485b6632d813d60d01a53eda0238fd4a9b2', 'NVDA size function')
    rec = records['ev_135e838a1e18421f25c8bd6470be6d4b290211e8d45fa321ee2aeb2de30aa186']
    need(rec['subject']['digest']['sha256'] == N and rec['normalized_result']['procedure']['address'] == '0x42614', 'NVDA REA')
    _, cell = file_bytes(nvda, 0x433fc, 4)
    need(0x432bc + struct.unpack('<i', cell)[0] == 0x4266d, 'class 0x80 size branch')
    _, instr = file_bytes(nvda, 0x4266d, 20)
    need(instr[:10] == bytes.fromhex('c6020131c04885f60f84') and
         instr[14:20] == bytes.fromhex('c70738000000'), 'conditional 56 byte size')
    _, body = file_bytes(cuda, 0x22ba82, 401)
    need(sha(body) == 'b48bbfbccb272904a266f0b02efe1b7e345fc089f4a48ee783341286d44b98e4', 'CUDA window')
    _, symbols = symbols_and_external_relocations(geforce)
    for a, name in ((0x6a1c1, '_NvRmAllocRoot'), (0x6a2bf, '_NvRmAlloc'),
                    (0x6a2ed, '_NvRmAlloc'), (0x6a0d8, '_NvRmFree')):
        entries = symbols.get(a, [])
        need(len(entries) == 1 and entries[0]['symbol']['name'] == name and
             entries[0]['external'] == 1 and entries[0]['type'] == 2, 'relocation')
    _, slot = file_bytes(geforce, 0x92088, 8)
    need(struct.unpack('<Q', slot)[0] == 0x6a222, 'file-backed vtable slot')
    return {'status': 'PASS_STATIC_DEVICE_ALLOCATION', 'geforce_sha256': G, 'nvda_sha256': N,
            'cuda_sha256': C, 'rea_sha256': REA, 'nvda_rea_sha256': OLD, 'header_sha256': HEADER,
            'functions': out, 'nvda_size_function_sha256': sha(b), 'cuda_window_sha256': sha(body),
            'class': '0x80', 'nonnull_parameter_bytes': 56, 'raw_vtable_slot': '0x92088',
            'private_RM_calls': 0, 'GPU_dispatches': 0,
            'scope': 'On-disk and modeled layout only; user allocation, live handles, loaded-driver identity and cleanup are unqualified.'}

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('geforce', 'nvda', 'cuda', 'rea', 'old-rea', 'header', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    need(a.out.parent.is_dir() and not a.out.exists(), 'fresh output')
    header = a.header.read_bytes()
    result = inspect(a.geforce.read_bytes(), a.nvda.read_bytes(), a.cuda.read_bytes(),
                     a.rea.read_bytes(), a.old_rea.read_bytes(), header)
    result['nvidia_515_model'] = layout(header, a.out.parent)
    with a.out.open('x') as f:
        json.dump(result, f, indent=2, sort_keys=True); f.write('\n')
    print(json.dumps(result, sort_keys=True))

if __name__ == '__main__': main()
