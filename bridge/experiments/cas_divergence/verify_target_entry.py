#!/usr/bin/env python3
"""Compare target-entry witness against a pinned native CPU oracle."""
import hashlib
import struct
from verify_branch_witness import verify_baseline

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
        if marker not in (0,1):raise ValueError('unexpected target marker')
        histogram[str(marker)]=histogram.get(str(marker),0)+1
    return {'status':'PASS','pattern':breport['pattern'],'rows':len(rows),'markers':histogram,
            'baseline_sha256':hashlib.sha256(baseline).hexdigest(),'trace_sha256':hashlib.sha256(trace).hexdigest(),
            'indirect_origin_proved':False,'resident_instructions_read_back':False,'all_paths_qualified':False}
