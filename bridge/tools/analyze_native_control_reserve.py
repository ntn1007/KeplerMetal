#!/usr/bin/env python3
"""Bind native listings to bytes and compare lexical control metrics, offline.

Forward join-interval overlap is a listing metric, NOT a dynamic CRS depth,
general upper bound, allocator certificate or hardware execution observation.
"""
from pathlib import Path
import argparse
import collections
import hashlib
import json
import re
import struct

ROOT = Path(__file__).resolve().parents[1]
LINE = re.compile(r'^([0-9a-f]{8}): ([0-9a-f]{8}) ([0-9a-f]{8})\s+(.*)$')
CONTROL = ['joinat', 'join', 'prebreak', 'precont', 'break', 'cont', 'call', 'preret', 'ret', 'exit', 'bra']


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def mesa_crs(depth):
    if depth <= 16: return 0
    if depth <= 32: return 1024
    return ((depth + 32)*16 + 511) & ~511


def analyze(folder):
    data = json.loads((folder / 'observations.json').read_text()); output = []
    for row in data['records']:
        capture = folder / row['function'] / 'capture'
        code = (capture / 'native.sass').read_bytes(); listing = capture / 'native.envydis.txt'
        assert sha(capture / 'native.sass') == row['code_SHA256']
        assert len(code) == row['code_bytes'] and sha(listing) == row['listing_SHA256']
        assert sha(capture / 'program-0.compiler-output.bin') == row['compiler_output_SHA256']
        instructions = {}; counts = collections.Counter(); intervals = []; branches = []
        for line in listing.read_text().splitlines():
            m = LINE.match(line)
            if not m: continue
            pc, lo, hi = (int(m.group(i),16) for i in [1,2,3]); text = m.group(4)
            assert pc not in instructions and pc % 8 == 0 and pc + 8 <= len(code)
            assert struct.unpack_from('<2I', code, pc) == (lo, hi), 'listing differs from code'
            instructions[pc] = text
            for op in CONTROL:
                if re.search(r'\b'+op+r'\b', text): counts[op] += 1
            join = re.search(r'\bjoinat 0x([0-9a-f]+)', text)
            if join:
                target = int(join.group(1),16)
                assert pc < target < len(code), 'non-forward join target needs separate analysis'
                intervals.append((pc, target))
            branch = re.search(r'\bbra 0x([0-9a-f]+)', text)
            if branch: branches.append((pc,int(branch.group(1),16)))
        assert len(instructions) == len(code)//8, 'incomplete native listing'
        assert all(target in instructions for _,target in intervals+branches), 'target not decoded'
        events = collections.Counter()
        for begin,end in intervals: events[begin] += 1; events[end] -= 1
        live = peak = 0; peak_pc = 0
        for pc in sorted(events):
            live += events[pc]
            if live > peak: peak,peak_pc = live,pc
        assert live == 0
        w = row['metadata_words']; nonlexical = {k:counts[k] for k in CONTROL if k not in ['joinat','join','bra','exit'] and counts[k]}
        output.append({'function':row['function'],'source_depth':row['source_depth'],
                       'observation_file':str((folder/'observations.json').relative_to(ROOT)),
                       'observation_SHA256':sha(folder/'observations.json'),'code_SHA256':row['code_SHA256'],
                       'listing_SHA256':row['listing_SHA256'],'native_code_bytes':len(code),
                       'native_word11':w[11],'native_frame':w[12],'native_spill':w[14],
                       'control_instruction_counts':dict(counts),'max_forward_join_intervals':peak,
                       'first_peak_PC':hex(peak_pc),'backward_branches':sum(b<=a for a,b in branches),
                       'unhandled_control_ops':nonlexical,'unknown_annotations':row['unknown_annotations'],
                       'mesa_rule_on_lexical_metric':mesa_crs(peak),
                       'mesa_rule_on_total_joinat_count':mesa_crs(counts['joinat']),
                       'synthetic_depth_relation_544_plus16d':w[11]==544+16*row['source_depth'],
                       'dynamic_CRS_depth_established':False})
    return output


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--observations',type=Path,nargs='+',required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results')
    records=[row for folder in a.observations for row in analyze(folder.resolve())]
    proof={'status':'PASS','scope':'Byte-bound static listing metrics; no new native construction or GPU dispatch',
           'records':records,'profiles':len(records),'analyzer_SHA256':sha(Path(__file__)),
           'GPU_execution':False,'dynamic_CRS_depth_established':False,
           'limits':['Lexical intervals do not establish actual SIMT stack depth or branch reachability',
                     'The Mesa CRS formula is from a different compiler/runtime and is a comparison, not a macOS allocator rule',
                     'Static operation counts cannot establish instruction execution or numerical correctness']}
    with out.open('x')as f:json.dump(proof,f,indent=2);f.write('\n')
    print(json.dumps({'status':'PASS','profiles':len(records),'dynamic_CRS_depth_established':False}))
