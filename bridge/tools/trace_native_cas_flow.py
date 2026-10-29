#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline CAS register-flow hypotheses; never authorizes a certificate or GPU dispatch."""
import argparse
import hashlib
import json
import re
import struct
from collections import deque
from pathlib import Path

from recognize_native_cas import air_contract, register_references, register_writes, verify_decoder


def sha(data):return hashlib.sha256(data).hexdigest()
def fail(message):raise ValueError(message)


def instructions_from_listing(code,listing):
    if not code or len(code)%64:fail('unsupported code size')
    instructions=[];next_offset=0
    for line in listing.splitlines():
        match=re.match(r'^([0-9a-f]{8}): ([0-9a-f]{8}) ([0-9a-f]{8})\s+(.*)$',line)
        if not match:continue
        offset=int(match[1],16);raw=struct.pack('<II',int(match[2],16),int(match[3],16))
        if offset!=next_offset or code[offset:offset+8]!=raw:fail('decoder coverage or bytes differ')
        next_offset+=8;op=re.sub(r'^B\s+','',match[4]).strip()
        if offset%64==0:
            if not op.startswith('sched '):fail('missing schedule')
            continue
        if '[unknown instruction]' in op or ('[unknown:' in op and
           (not ('ld lock ' in op or 'st unlock ' in op) or '[unknown: 00000000 01000000]' not in op)):
            fail('unsupported undecoded instruction')
        instructions.append((offset,op.split(' [unknown:')[0]))
    if next_offset!=len(code) or len(instructions)!=len(code)//8-len(code)//64:fail('incomplete decoder coverage')
    if max((r for _,op in instructions for r in register_references(op)),default=0)>=24:fail('register floor exceeds 24')
    return instructions


BRANCH=re.compile(r'(?:(?:\$p\d+|\(not \$p\d+\)) )?bra (0x[0-9a-f]+)')
COMPARE=re.compile(r'set \$p\d+ 0x1 eq [us]32 \$r(\d+) \$r(\d+)')
COPY=re.compile(r'mov b32 \$r(\d+) \$r(\d+)')


def trace_region(instructions,start,end,original,expected):
    """Must-alias over direct branches in a closed, JOIN-free instruction slice.

    The caller must establish the entry facts separately. An unsupported
    operation or branch escaping the slice is a refusal, not a proof of safety.
    """
    if not (0<=start<end<len(instructions)) or original==expected:fail('invalid flow bounds')
    offsets={off:i for i,(off,_) in enumerate(instructions)}
    start_off,end_off=instructions[start][0],instructions[end][0]
    for i,(off,op) in enumerate(instructions):
        unpredicated=re.sub(r'^(?:\$p\d+ |\(not \$p\d+\) )','',op)
        opcode=unpredicated.split()[0]
        if opcode in {'call','cal','ret','brk','break','breakaddr','prebrk','preret','brx','trap'}:
            fail('unmodelled nonlocal control flow')
        if 'bra ' in op:
            m=BRANCH.fullmatch(op)
            if not m:fail('indirect or unsupported branch')
            target=int(m[1],16);target=target+8 if target%64==0 else target
            if start_off<=target<=end_off and not start<=i<end:fail('branch enters tracked slice')
        if opcode=='joinat':
            # Predicate-dependent reconvergence has no model here, including
            # a target outside this slice or at its assumed entry.
            if unpredicated!=op:fail('predicated reconvergence is unmodelled')
            m=re.fullmatch(r'joinat (0x[0-9a-f]+)',unpredicated)
            if not m:fail('unsupported reconvergence target')
            target=int(m[1],16);target=target+8 if target%64==0 else target
            # Entry reconvergence remains an explicit, unproved assumption;
            # a target inside the slice invalidates this simplified model.
            if start_off<target<=end_off:fail('reconvergence target enters tracked slice')
    states={start:frozenset([original])};pending=deque([start]);edges=set()
    while pending:
        i=pending.popleft()
        if i==end:continue
        off,op=instructions[i]
        unpredicated=re.sub(r'^(?:\$p\d+ |\(not \$p\d+\) )','',op)
        if unpredicated.split()[0] in {'join','joinat','exit','call','ret','break','trap'}:fail('unsupported control flow in tracked slice')
        writes=register_writes(op)
        if writes is None:fail('unrecognized register effects')
        if expected in writes:fail('comparison input overwritten')
        incoming=states[i];after=set(incoming)-writes
        m=COPY.fullmatch(op)
        if m and int(m[2]) in incoming:after.add(int(m[1]))
        branch=BRANCH.fullmatch(op)
        if branch:
            target=int(branch[1],16);target=target+8 if target%64==0 else target
            if target not in offsets:fail('invalid branch target')
            successors=[offsets[target]]
            if not op.startswith('bra '):successors.append(i+1)
        else:successors=[i+1]
        for successor in successors:
            if not start<=successor<=end:fail('branch leaves tracked slice')
            edges.add((off,instructions[successor][0]));new=frozenset(after)
            if successor not in states:states[successor]=new;pending.append(successor)
            else:
                merged=states[successor]&new
                if merged!=states[successor]:states[successor]=merged;pending.append(successor)
    if end not in states:fail('comparison unreachable')
    return {'aliases_at_comparison':sorted(states[end]),'reachable_instructions':len(states),
            'direct_edges':len(edges),'entry_offset':start_off,'comparison_offset':end_off}


def analyze(code,listing,air):
    ins=instructions_from_listing(code,listing);component=air.get('expected_output_component')
    if not air.get('qualified') or type(component) is not int or not 0<=component<=3:fail('unsupported AIR contract')
    hypotheses=[];refusals=[]
    for i,(off,op) in enumerate(ins):
        match=re.fullmatch(r'ld lock \$p(\d+) \$r(\d+) s\[(0x[0-9a-f]+|\$r[0-9]+)\]',op)
        if not match or i+6>=len(ins):continue
        pred,old,address=match.groups();old=int(old)
        eq=re.fullmatch(r'\$p'+pred+r' set b32 \$r(\d+) eq s32 \$r'+str(old)+r' \$r(\d+)',ins[i+1][1])
        if not eq:continue
        temp,expected=map(int,eq.groups())
        select=re.fullmatch(r'\$p'+pred+r' slct b32 \$r(\d+) \$r(\d+) \$r'+str(old)+r' ne s32 \$r'+str(temp),ins[i+2][1])
        if not select:continue
        update=int(select[1])
        unlock=re.fullmatch(r'\$p'+pred+r' st unlock \$p(\d+) s\['+re.escape(address)+r'\] \$r'+str(update),ins[i+3][1])
        if not unlock or ins[i+4][1]!='(not $p'+unlock[1]+') bra '+hex(off) or ins[i+5][1]!='join nop':continue
        if len({old,expected,temp,update})!=4 or (address.startswith('$r') and int(address[2:]) in {old,expected,temp,update}):continue
        for end in range(i+6,len(ins)-1):
            compare=COMPARE.fullmatch(ins[end][1])
            if not compare or int(compare[1])!=expected:continue
            saved=int(compare[2]);patch,patchop=ins[end+1]
            displaced=re.fullmatch(r'mov b32 \$r(\d+) c2\[(0x[0-9a-f]+)\]',patchop)
            if not displaced or int(displaced[1]) in (expected,saved):continue
            try:
                trace=trace_region(ins,i+6,end,old,expected)
                if saved not in trace['aliases_at_comparison']:fail('saved register is not a must-alias')
                stores=[]
                for n in range(end+2,len(ins)):
                    sm=re.fullmatch(r'st b128 wb g\[\$r(\d+)d\] \$r(\d+)q',ins[n][1])
                    if sm:stores.append((n,int(sm[1]),int(sm[2])))
                if len(stores)!=1:fail('output store is not unique')
                store,address_base,base=stores[0]
                if expected!=base+component or address_base<=expected<address_base+2:fail('output/address register mismatch')
                for n,(_,later) in enumerate(ins[end+2:],start=end+2):
                    if n!=store and (register_writes(later) is None or expected in register_references(later)):
                        fail('unqualified later use')
                for n,(source,branch) in enumerate(ins):
                    m=re.fullmatch(r'(?:(?:\$p\d+|\(not \$p\d+\)) )?(?:bra|joinat) (0x[0-9a-f]+)',branch)
                    if m:
                        target=int(m[1],16)
                        if target in (patch,patch+8) or (source>patch and target<=patch):fail('redirect control-flow conflict')
                hypotheses.append({'CAS_offset':off,'lock_result_register':old,'saved_register':saved,
                    'expected_register':expected,'redirect_offset':patch,'displaced_destination_register':int(displaced[1]),
                    'displaced_constant_offset':int(displaced[2],16),'output_store_offset':ins[store][0],'trace':trace})
            except ValueError as error:
                refusals.append({'CAS_offset':off,'comparison_offset':ins[end][0],'reason':str(error)})
    return {'status':'HYPOTHESIS_ONLY' if len(hypotheses)==1 else 'REFUSED',
            'hypotheses':hypotheses,'refusals':refusals,'certificate_authorized':False,'GPU_dispatch':False,
            'limitations':['entry facts and reconvergence are assumptions, not proven',
                           'decoder semantics, scheduling, AIR-to-SASS correspondence and arbitrary aliases remain unproved',
                           'per-shader GPU qualification and runtime checks remain necessary']}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--diagnosis',type=Path,required=True);parser.add_argument('--decoder',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    d=args.diagnosis.resolve();out=args.out.resolve()
    if out.exists() or not out.parent.is_dir():fail('fresh output required')
    code=(d/'native.sass').read_bytes();listing=(d/'native.asm').read_text()
    typed=(d/'typed-air.json').read_bytes();diagnosis=json.loads((d/'diagnosis.json').read_text())
    if not verify_decoder(code,listing,args.decoder):fail('pinned decoder replay failed')
    air=air_contract(json.loads(typed),diagnosis['function'])
    if air!=diagnosis['AIR'] or sha(code)!=diagnosis['artifact_SHA256']['native.sass'] or \
       sha(typed)!=diagnosis['artifact_SHA256']['typed-air.json']:fail('diagnosis snapshot differs')
    result=analyze(code,listing,air)
    result.update({'native_SHA256':sha(code),'listing_SHA256':sha(listing.encode()),
                   'typed_AIR_SHA256':sha(typed),'pinned_decoder_reproduced':True})
    with out.open('x') as stream:json.dump(result,stream,indent=2,sort_keys=True);stream.write('\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
