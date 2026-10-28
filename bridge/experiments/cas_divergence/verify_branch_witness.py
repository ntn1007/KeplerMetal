#!/usr/bin/env python3
"""CPU oracle for the bounded native and indirect-branch witness outputs."""
import hashlib
import json
import struct
from pathlib import Path

def verify_baseline(raw,report):
    if report['status']!='COMPLETED' or report['device']!='NVIDIA GeForce GTX 880M' or report['registry_id']!=4294968416 or \
       report['GPU_dispatch'] is not True or report['command_status']!=4 or report['mode']!='baseline' or \
       (report['threads'],report['groups'],report['variant'],report['seed'])!=(33,3,1,0x1234) or report['pattern'] not in (0,2,3,4):
        raise ValueError('baseline report differs')
    if len(raw)!=1712 or raw[:64]!=b'\xa5'*64 or raw[-64:]!=b'\xa5'*64:raise ValueError('baseline guard differs')
    rows=[]
    for i in range(99):
        row=struct.unpack_from('<4I',raw,64+16*i);group,tid=divmod(i,33)
        initial=(0x1234+group*0x10001+tid*13)&0xffffffff
        active=report['pattern']==2 and tid%2==0 or report['pattern']==3 and tid<17
        expected=(initial^1,0,initial,i^0x6d2b79f5^(0x80000000 if active else 0))
        if row!=expected:raise ValueError('baseline numerical result differs')
        rows.append(row)
    return rows

def compare(baseline,breport,trace,treport):
    rows=verify_baseline(baseline,breport)
    if treport['mode']!='trace' or treport['pattern']!=breport['pattern'] or \
       any(treport[k]!=breport[k] for k in ('status','device','registry_id','GPU_dispatch','command_status','threads','groups','variant','seed')):
        raise ValueError('trace report differs')
    if len(trace)!=1712 or trace[:64]!=b'\xa5'*64 or trace[-64:]!=b'\xa5'*64:raise ValueError('trace guard differs')
    histogram={}
    for i,base in enumerate(rows):
        row=struct.unpack_from('<4I',trace,64+16*i)
        if (row[0],row[2],row[3])!=(base[0],base[2],base[3]):raise ValueError('trace changed non-witness output')
        marker=row[1]
        if marker not in (1,0x98,0xb8,0x30):raise ValueError('unexpected marker')
        histogram[str(marker)]=histogram.get(str(marker),0)+1
    if breport['pattern']==0 and histogram!={'1':99}:raise ValueError('inactive control unexpectedly branched')
    return {'status':'PASS','pattern':breport['pattern'],'rows':len(rows),'markers':histogram,
            'baseline_sha256':hashlib.sha256(baseline).hexdigest(),'trace_sha256':hashlib.sha256(trace).hexdigest(),
            'unmodified_branch_instruction_readback':False,'all_paths_qualified':False}

def main():
    import argparse
    p=argparse.ArgumentParser(description=__doc__)
    for key in ('baseline','trace','out'):p.add_argument('--'+key,type=Path,required=True)
    a=p.parse_args();result=compare((a.baseline/'output.bin').read_bytes(),json.loads((a.baseline/'report.json').read_text()),
                                    (a.trace/'output.bin').read_bytes(),json.loads((a.trace/'report.json').read_text()))
    with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(result))

if __name__=='__main__':main()
