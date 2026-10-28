#!/usr/bin/env python3
"""Inspect a captured indirect branch and possible literal table offline."""
import argparse
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

BRIDGE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BRIDGE / 'tools'))
from recognize_native_cas import verify_decoder
from trace_native_cas_flow import instructions_from_listing


def require(ok, reason):
    if not ok: raise ValueError(reason)


def sections(blob):
    require(len(blob) >= 32 and struct.unpack_from('<I', blob, 0)[0] in (7, 8, 9) and
            struct.unpack_from('<I', blob, 4)[0] == len(blob), 'invalid container header')
    offset = 8; out = {}; visited = set()
    while True:
        require(offset not in visited and offset <= len(blob)-16 and len(visited)<32, 'invalid section link')
        visited.add(offset); next_offset, kind, size = struct.unpack_from('<QII', blob, offset)
        require(size <= len(blob)-offset-16 and kind not in out, 'invalid or repeated section')
        out[kind] = blob[offset+16:offset+16+size]
        if not next_offset:
            end=offset+16+size
            require((end == len(blob) or ((end+7)&~7) == len(blob)) and
                    not any(blob[end:]), 'trailing container data')
            return out
        require(next_offset >= 16+size and next_offset <= len(blob)-offset, 'section link out of bounds')
        offset += next_offset


def examine(instructions, table):
    require(len(table) == 12, 'expected three table words')
    by_offset = dict(instructions)
    require(len(by_offset) == len(instructions), 'duplicate instruction offset')
    expected = {0x268:'add b32 $r0 $r0 0xfffffffe',
                0x270:'min u32 $r0 $r0 0x2',
                0x278:'shl b32 $r0 $r0 clamp 0x2',
                0x288:'ld b32 $r1 c0[$r0]',
                0x290:'bra $r1 0x0'}
    require(all(by_offset.get(offset) == op for offset, op in expected.items()), 'instruction slice differs')
    require([off for off, op in instructions if re.search(r'\bbra \$r\d+', op)] == [0x290],
            'indirect branch count differs')
    targets = list(struct.unpack('<III', table))
    require(targets == [0x298, 0x2b8, 0x330], 'candidate table differs')
    require(all(t in by_offset and t % 64 != 0 for t in targets), 'candidate is not a decoded instruction')
    # This inventory covers direct branches and joinat with a literal target,
    # not unmodelled reconvergence, hidden control flow or the indirect branch.
    entering = []
    for off, op in instructions:
        for target in re.findall(r'\b(?:bra|joinat) (0x[0-9a-f]+)', op):
            if 0x270 <= int(target, 16) <= 0x290: entering.append([off, int(target, 16)])
    require(not entering, 'direct entry may bypass index calculation')
    return {'status':'OBSERVED', 'branch_offset':0x290, 'index_slice_start':0x268,
            'conditional_index_offsets':[0,4,8], 'candidate_table_section':0x10006,
            'candidate_targets':targets, 'candidate_targets_are_decoded_instructions':True,
            'simple_direct_entries_to_slice':entering, 'constant_bank_binding_proved':False,
            'branch_target_semantics_proved':False, 'all_entries_to_slice_proved':False,
            'GPU_execution_proved':False, 'authorizes_repair':False,
            'limits':'Conditional arithmetic and candidate table only; no live c0 binding, register-indirect branch semantics, complete CFG or resident GPU readback.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('container','code','listing','decoder','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();blob=a.container.read_bytes();code=a.code.read_bytes();listing=a.listing.read_text()
    require(hashlib.sha256(blob).hexdigest()=='adc3551baff3d2e6de1e06fd158b80d9fe6f15df744d9e28b40dfe92de327821', 'captured container differs')
    require(hashlib.sha256(code).hexdigest()=='83fedb1873bf54ae9975d3f44bd8e8512a9639903afee18d2decef4fbcdd2eb2', 'captured program differs')
    parts=sections(blob);require(parts.get(0x10005)==code and 0x10006 in parts, 'captured sections differ')
    require(verify_decoder(code,listing,a.decoder), 'decoder replay failed')
    result=examine(instructions_from_listing(code,listing),parts[0x10006])
    result.update({'container_sha256':hashlib.sha256(blob).hexdigest(),
                   'program_sha256':hashlib.sha256(code).hexdigest(),
                   'candidate_section_sha256':hashlib.sha256(parts[0x10006]).hexdigest(),
                   'decoder_sha256':hashlib.sha256(a.decoder.read_bytes()).hexdigest(),
                   'listing_sha256':hashlib.sha256(listing.encode()).hexdigest(),
                   'decoder_replayed':True})
    with a.out.open('x') as out:json.dump(result,out,indent=2,sort_keys=True);out.write('\n')
    print(json.dumps(result))


if __name__ == '__main__': main()
