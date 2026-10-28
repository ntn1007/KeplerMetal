#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Classify raw Metal CAS output against a lane-specific CPU oracle."""
import argparse
import hashlib
import json
import struct
from pathlib import Path


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,required=True);parser.add_argument('--outputs',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);args=parser.parse_args()
    if args.out.exists() or not args.out.parent.is_dir():raise ValueError('fresh output required')
    data=json.loads(args.report.read_text());runs=data['runs']
    expected={(l,p,v,r) for l in (33,128,1024) for p in range(4) for v in range(2) for r in range(2)}
    seen=set();rows=[];totals={name:0 for name in ('active_expected','inactive_expected','success','final','witness','guard_bytes')}
    for run in runs:
        local,pattern,variant,repeat=(run[k] for k in ('local','pattern','variant','repeat'))
        key=(local,pattern,variant,repeat)
        if key not in expected or key in seen or run['groups']!=3 or run['status']!=4 or run['seed']!=0x1234+37*repeat:
            raise ValueError('unexpected geometry or command status')
        seen.add(key);name=run['file'];rel=Path(name)
        if rel.name!=name or name!=f'l{local}-p{pattern}-v{variant}-r{repeat}.bin':raise ValueError('unsafe output name')
        raw=(args.outputs/rel).read_bytes();n=local*3
        if len(raw)!=n*16+128:raise ValueError('unexpected output length')
        wrong={k:0 for k in totals};wrong['guard_bytes']=sum(x!=0xa5 for x in raw[:64]+raw[-64:])
        values=struct.unpack('<%dI'%(n*4),raw[64:-64]);active_count=0
        for i in range(n):
            compare,success,final,witness=values[i*4:i*4+4];group,tid=divmod(i,local)
            initial=(run['seed']+group*0x10001+tid*13)&0xffffffff;replacement=initial^0x55667788
            active=pattern==1 or (pattern==2 and tid%2==0) or (pattern==3 and tid<(local+1)//2)
            active_count+=active
            wrong['active_expected' if active else 'inactive_expected']+=compare!=(initial if active else initial^variant)
            wrong['success']+=success not in (0,1) or ((not active or variant==1) and success!=0)
            wrong['final']+=final!=(replacement if active and success==1 else initial)
            wrong['witness']+=witness!=(i^0x6d2b79f5^(0x80000000 if active else 0))
        for k in totals:totals[k]+=wrong[k]
        rows.append({'local':local,'pattern':pattern,'variant':variant,'repeat':repeat,'elements':n,
                     'expected_active':active_count,'mismatches':wrong,'output_SHA256':hashlib.sha256(raw).hexdigest()})
    if seen!=expected:raise ValueError('missing test configurations')
    result={'status':'PASS' if not any(totals.values()) else 'OBSERVED_MISMATCH','device':data['device'],
            'registry_id':data['registry_id'],'pipeline_max_threads':data['pipeline_max_threads'],
            'threadgroup_memory_bytes':data['threadgroup_memory_bytes'],'dispatches':len(rows),
            'checked_words':sum(x['elements']*4 for x in rows),'totals':totals,'cases':rows,
            'oracle_allows_weak_CAS_spurious_failure':True,'performance_benchmark':False}
    with args.out.open('x') as out:json.dump(result,out,indent=2,sort_keys=True);out.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2))


if __name__=='__main__':main()
