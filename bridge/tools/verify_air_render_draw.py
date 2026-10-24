#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent typed draw/reset order, state preservation and arithmetic oracle."""
from pathlib import Path
import struct
from public_large_scratch import read
from verify_air_reset_dataflow import CASES as RESET_CASES,expected as initial_expected,verify as verify_flow

PROFILE='typed-render-draw-dataflow-air28-v1'
CASES=RESET_CASES+(('draw_only',16,16,3,0,32),('ordered_reset',16,16,3,0,32),('ordered_draw',16,16,3,0,32))
VALID={'single','prefix','full','branch','mask3','tail','draw_only','ordered_reset','ordered_draw'}


def expected(case,execute):
    assert case in CASES
    name,count,capacity,seed,mask,width=case
    basecase=case if case in RESET_CASES else('full',16,16,9,0,32)
    result=[bytearray(b)for b in initial_expected(basecase,False)[0]]
    indices=[int(format(i,'04b')[::-1],2)^(seed&15)if i<16 else i+16 for i in range(64)]
    for i,index in enumerate(indices):struct.pack_into('<I',result[2],64+4*i,index)
    modified=[]
    if execute:
        for gid in range(count):
            index=indices[gid];x=((gid*1664525+seed)&0xffffffff)^index;selected=(x&mask)==0
            if name in VALID and index<capacity:
                offset=64+index*64
                identity=0 if name=='ordered_draw'else struct.unpack_from('<Q',result[0],offset+32)[0]
                if selected and name!='ordered_reset':
                    first=5+3*((x>>3)&1);vertices=3*((x>>4)&3);instances=(x>>6)&1;base=(x>>8)&3
                    result[0][offset:offset+64]=struct.pack('<8IQ6I',0x4b505353,0,vertices,instances,first,0,base,0,identity,*([0]*6))
                else:result[0][offset:offset+64]=bytes(64)
                modified.append(index)
            x=x^0xa511e9b3 if selected else(x+0x7f4a7c15)&0xffffffff
            shift=(gid&15)+1;value=(((x<<shift)|(x>>(32-shift)))^(index*0x9e3779b9))&0xffffffff
            struct.pack_into('<I',result[1],64+4*gid,value)
    assert len(modified)==len(set(modified)),'One invocation per record required'
    return list(map(bytes,result)),modified


def verify(path):
    path=Path(path);assert read(path/'inputs.json')['profile']==PROFILE
    proof=verify_flow(path,cases=CASES,recipe=expected)
    if proof['mode']!='inspect':
        proof['modified_records']=proof.pop('reset_records')
        draws=resets=identities=0
        for case in CASES:
            blobs,slots=expected(case,proof['mode']=='execute')
            for index in slots:
                words=struct.unpack_from('<8IQ6I',blobs[0],64+index*64)
                if words[0]==0x4b505353:
                    draws+=1;identities+=int(words[8]!=0)
                else:assert not any(words);resets+=1
        proof.update(draw_records=draws,reset_records=resets,nonzero_state_identities_preserved=identities,
            native_Apple_ICB_ABI=False,downstream_render=False,performance_benchmark=False)
    return proof
