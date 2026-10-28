#!/usr/bin/env python3
"""CPU oracle for the bounded CB0 witness output; never dispatch GPU work."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

def verify(raw,report):
    if report['status']!='COMPLETED' or report['device']!='NVIDIA GeForce GTX 880M' or report['registry_id']!=4294968416 or \
       report['GPU_dispatch'] is not True or report['command_status']!=4 or \
       (report['threads'],report['groups'],report['pattern'],report['variant'],report['seed'])!=(33,3,0,1,0x1234):
        raise ValueError('GPU report profile differs')
    if report['mode'] not in ('control','cb0') or len(raw)!=128+99*16:raise ValueError('output shape differs')
    guard=sum(x!=0xa5 for x in raw[:64]+raw[-64:]);values=struct.unpack('<396I',raw[64:-64])
    rows=[values[i:i+4] for i in range(0,len(values),4)]
    witness=sum(row[3]!=(i^0x6d2b79f5) for i,row in enumerate(rows))
    triplets={tuple(row[:3]) for row in rows};uniform=len(triplets)==1
    triplet=list(next(iter(triplets))) if uniform else None
    expected=[0x111,0x222,0x333] if report['mode']=='control' else [0x298,0x2b8,0x330]
    matches=sum(tuple(row[:3])!=tuple(expected) for row in rows)
    if guard or witness or not uniform:raise ValueError('guard, witness or consistency failed')
    if report['mode']=='control' and matches:raise ValueError('known-value control failed')
    return {'status':'PASS' if not matches else 'OBSERVED_DIFFERENT', 'mode':report['mode'],
            'rows':len(rows),'checked_words':len(values),'guard_mismatches':guard,'witness_mismatches':witness,
            'triplet':triplet,'expected_triplet':expected,'mismatched_rows':matches,
            'candidate_section_matches':(matches==0 if report['mode']=='cb0' else None),
            'output_sha256':hashlib.sha256(raw).hexdigest(),'performance_benchmark':False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    result=verify((a.run/'output.bin').read_bytes(),json.loads((a.run/'report.json').read_text()))
    with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(result))

if __name__=='__main__':main()
