#!/usr/bin/env python3
"""Propose a pinned native control reserve; never certify or apply it.

The path abstraction models forward SSY/JOIN targets and independent predicate
outcomes. Warp masks, predicate dataflow and divergent BRA tokens are omitted.
Its finite depth is NOT a hardware SIMT bound. A proposal requires separate
numerical GPU qualification and never authorizes arbitrary shader execution.
"""
from pathlib import Path
import argparse
import collections
import hashlib
import json
import re
import struct

ROOT = Path(__file__).resolve().parents[1]
DRIVER = "2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054"
SOURCE_SHA256 = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
LINE = re.compile(r'^([0-9a-f]{8}): ([0-9a-f]{8}) ([0-9a-f]{8})\s+(.*)$')
PRED = re.compile(r'^(\(not \$p([0-6])\)|\$p([0-6]))\s+')


class Refused(ValueError):
    def __init__(self, gate):
        self.gate = gate
        super().__init__(gate)


def need(test, gate):
    if not test:
        raise Refused(gate)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def predicate(text):
    m = PRED.match(text)
    if not m:
        return 7, text
    index = int(m.group(2) or m.group(3))
    return index + (8 if m.group(2) is not None else 0), text[m.end():]


def decode(code, listing, expected_hash):
    need(digest(code) == expected_hash, "code_hash")
    need(64 <= len(code) <= 104000 and len(code) % 64 == 0, "code_size")
    need('[unknown' not in listing, "unknown_decode")
    instructions = {}
    for line in listing.splitlines():
        m = LINE.match(line)
        if not m:
            continue
        pc, lo, hi = [int(m.group(i), 16) for i in [1, 2, 3]]
        need(pc not in instructions and pc % 8 == 0 and pc + 8 <= len(code), "listing_address")
        need(struct.unpack_from('<II', code, pc) == (lo, hi), "listing_word")
        word = lo | (hi << 32)
        text = re.sub(r'^[A-Z]+\s+', '', m.group(4))
        scheduled = word & 15 == 7 and word >> 60 == 2
        # Native code can target schedule words and put an unreachable tail BRA
        # on a64-byte boundary. NAK's own layout convention is not aHW rule.
        need(scheduled == text.startswith('sched '), "schedule_encoding")
        if scheduled:
            instructions[pc] = ('SCHEDULE', None, 7)
            continue
        joined, encoded_pred = bool(word & 16), (word >> 10) & 15
        need(joined == text.startswith('join '), "join_encoding")
        if joined:
            text = text[5:]
        printed_pred, text = predicate(text)
        need(printed_pred == encoded_pred and encoded_pred != 15, "predicate_encoding")
        kind, target = ('JOIN' if joined else 'STEP'), None
        if word & 7 == 7:
            need(not joined and word & 8 == 0, "exec_modifiers")
            opcode = word >> 58
            need(opcode in [0x10, 0x18, 0x20], "unsupported_exec_opcode")
            base_mask = 7 | (15 << 10) | (63 << 58)
            if opcode in [0x10, 0x20]:
                base_mask |= 15 << 5
                need((word >> 5) & 15 == 15, "exec_flags")
            if opcode in [0x10, 0x18]:
                base_mask |= ((1 << 24) - 1) << 26
                rel = (word >> 26) & 0xffffff
                if rel & 0x800000:
                    rel -= 1 << 24
                target = pc + 8 + rel
            need(word & ~base_mask == 0, "exec_reserved_bits")
            if opcode == 0x18:
                need(encoded_pred == 7, "predicated_joinat")
                match = re.fullmatch(r'joinat 0x([0-9a-f]+)', text)
                need(match is not None and int(match[1], 16) == target, "joinat_target")
                need(pc < target < len(code), "joinat_forward")
                kind = 'PUSH'
            elif opcode == 0x10:
                match = re.fullmatch(r'bra 0x([0-9a-f]+)', text)
                need(match is not None and int(match[1], 16) == target, "branch_target")
                kind = 'BRANCH'
            else:
                need(text == 'exit', "exit_encoding")
                kind = 'EXIT'
        else:
            need(not re.search(r'\b(joinat|bra|exit|call|ret|prebreak|precont|break|cont|brx)\b', text),
                 "control_text_mismatch")
        instructions[pc] = kind, target, encoded_pred
    need(len(instructions) == len(code) // 8, "incomplete_listing")
    for kind, target, pred in instructions.values():
        if target is not None:
            need(target in instructions, "target_not_instruction")
    return instructions


def region_structure(instructions):
    intervals = [(pc, target) for pc, (kind, target, _) in instructions.items() if kind == 'PUSH']
    parents, depth = [], 0
    for begin, end in sorted(intervals):
        while parents and begin >= parents[-1]:
            parents.pop()
        need(not parents or end <= parents[-1], "crossing_regions")
        parents.append(end)
        depth = max(depth, len(parents))
    return len(intervals), depth


def path_abstraction(instructions, max_states=100000, max_depth=256):
    pending = collections.deque([(0, ())])
    seen = set()
    peak = exits = 0
    while pending:
        pc, stack = pending.popleft()
        if (pc, stack) in seen:
            continue
        need(len(seen) < max_states, "abstract_state_cap")
        need(len(stack) <= max_depth, "abstract_depth_cap")
        need(pc in instructions, "abstract_out_of_range")
        seen.add((pc, stack))
        peak = max(peak, len(stack))
        kind, target, pred = instructions[pc]
        if pred != 7 and kind in ['JOIN', 'BRANCH', 'EXIT']:
            pending.append((pc + 8, stack))
        if kind == 'PUSH':
            pending.append((pc + 8, stack + (target,)))
        elif kind == 'JOIN':
            need(stack, "abstract_underflow")
            pending.append((stack[-1], stack[:-1]))
        elif kind == 'BRANCH':
            pending.append((target, stack))
        elif kind == 'EXIT':
            exits += 1
        else:
            pending.append((pc + 8, stack))
    need(exits > 0, "no_abstract_exit")
    return peak, len(seen), exits


def mesa_reference_crs(depth):
    if depth <= 16:
        return 0
    if depth <= 32:
        return 1024
    return ((depth + 32) * 16 + 511) & ~511


def propose(code, listing, words, expected_hash):
    need(isinstance(words, (list, tuple)) and len(words) == 58
         and all(type(v) is int and 0 <= v <= 0xffffffff for v in words),
         "metadata_integer_words")
    need(len(words) == 58 and words[0] == len(code) // 8 - 1 and 1 <= words[7] <= 63,
         "metadata_code_registers")
    need(0 <= words[11] <= 4096 and 0 <= words[12] <= 4656 and words[12] == words[13]
         and 0 <= words[14] <= words[12] and words[9] == 64 * words[12] + words[11], "metadata_allocation")
    instructions = decode(code, listing, expected_hash)
    count, lexical = region_structure(instructions)
    peak, states, exits = path_abstraction(instructions)
    proposed = max(words[11], max(0, mesa_reference_crs(peak) - 512))
    need(proposed <= 4096 and (proposed == words[11] or proposed % 512 == 0), "proposal_policy_limit")
    return {'status': 'PROPOSAL_REQUIRES_GPU_QUALIFICATION' if proposed > words[11] else 'KEEP_NATIVE_PROPOSAL',
            'code_SHA256': expected_hash, 'code_bytes': len(code), 'metadata_SHA256': digest(struct.pack('<58I', *words)),
            'native_control': words[11], 'native_frame': words[12], 'GPRs': words[7],
            'region_count': count, 'maximum_forward_intervals': lexical,
            'maximum_abstract_path_depth': peak, 'abstract_states': states, 'abstract_exit_states': exits,
            'Mesa_reference_CRS_on_abstract_depth': mesa_reference_crs(peak), 'proposed_metadata_control': proposed,
            'native_prepared_CRS_relation': ((words[11] + 511) & ~511) + 512,
            'proposed_prepared_CRS_relation': ((proposed + 511) & ~511) + 512,
            'hardware_depth_proven': False, 'hardware_upper_bound_certified': False,
            'automatic_runtime_application': False, 'GPU_work_by_analyzer': 0,
            'limitations': ['Independent predicate choices; no predicate dataflow or warp-mask model',
                           'Divergent BRA tokens are not modeled',
                           'Mesa sizing is a cross-compiler hypothesis, not NVIDIA/macOS certification',
                           'Observed native success can require less than this deliberately coarse proposal',
                           'No physical VRAM usage or performance conclusion']}


def analyze_observations(folder):
    observed = json.loads((folder / 'observations.json').read_text())
    need(observed['driver_SHA256'] == DRIVER, "driver_profile")
    records = []
    for row in observed['records']:
        path = folder / row['function'] / 'capture'
        code = (path / 'native.sass').read_bytes()
        listing = path / 'native.envydis.txt'
        try:
            need(digest(listing.read_bytes()) == row['listing_SHA256'] and row['unknown_annotations'] == 0,
                 "listing_hash")
            result = propose(code, listing.read_text(), row['metadata_words'], row['code_SHA256'])
        except Refused as exc:
            result = {'status': 'REFUSED', 'gate': exc.gate, 'code_SHA256': digest(code),
                      'automatic_runtime_application': False, 'GPU_work_by_analyzer': 0}
        records.append({'function': row['function'], 'observations_SHA256': digest((folder / 'observations.json').read_bytes()),
                        **result})
    return records


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--observations', type=Path, nargs='+', required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    out = a.out.resolve()
    out.relative_to(ROOT / 'results')
    records = [r for folder in a.observations for r in analyze_observations(folder.resolve())]
    need(digest(Path(__file__).read_bytes()) == SOURCE_SHA256, "analyzer_source_changed")
    proof = {'status': 'ANALYZED', 'records': records, 'profiles': len(records),
             'refused': sum(r['status'] == 'REFUSED' for r in records),
             'analyzer_SHA256': SOURCE_SHA256, 'GPU_work': 0,
             'hardware_upper_bound_certified': False, 'automatic_runtime_application': False,
             'full_objective_complete': False}
    with out.open('x') as f:
        json.dump(proof, f, indent=2)
        f.write('\n')
    print(json.dumps({k: v for k, v in proof.items() if k != 'records'}, indent=2))
