#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reaudit serialized vertex-transition receipts and exact image controls."""
from pathlib import Path
from datetime import datetime
import argparse
import json
import struct
import subprocess
import sys
from public_large_scratch import read, sha, write
from verify_vertex_binding_render import MODES, EXTRA_MODES
ALL_MODES = MODES + EXTRA_MODES


def audit(root, build):
    root=Path(root);build=Path(build);bm=read(build/'inputs.json');trials=[];intervals=[];images={};proofs=[]
    for repeat in range(2):
        for mode in ALL_MODES:
            p=root/str(repeat)/mode;inputs=read(p/'inputs.json');receipt=read(p/'execution/manifest.json')
            assert inputs['source_build_inputs_SHA256']==sha(build/'inputs.json') and inputs['static_library_SHA256']==bm['static_library_SHA256']
            code='import sys,json;sys.path.insert(0,sys.argv[1]);from verify_vertex_binding_render import verify;print(json.dumps(verify(sys.argv[2])))'
            check=subprocess.run([sys.executable,'-I','-c',code,str(p/'oracles'),str(p)],capture_output=True,text=True)
            assert check.returncode==0,(str(p),check.stderr)
            proof=json.loads(check.stdout);assert proof['status']=='PASS' and proof['mode']==mode
            image=(p/'outputs/image.bin').read_bytes();images[repeat,mode]=image
            begin=datetime.fromisoformat(receipt['started_at']);end=datetime.fromisoformat(receipt['completed_at']);assert begin<=end
            intervals.append((begin,end,repeat,mode));trials.append({'repeat':repeat,'mode':mode,'receipt_SHA256':sha(p/'execution/manifest.json'),'result_SHA256':sha(p/'results.json'),'image_SHA256':sha(p/'outputs/image.bin')});proofs.append(proof)
    intervals.sort()
    for previous,current in zip(intervals,intervals[1:]):assert previous[1]<=current[0],(previous,current)
    pairs=0;changes={}
    for repeat in range(2):
        for first,second in [('gpu','native'),('no_dispatch','no_dispatch_native'),('disabled','disabled_native'),('foreign','foreign_native'),('reverse','reverse_native'),('reverse_no_dispatch','reverse_no_dispatch_native')]:
            assert images[repeat,first]==images[repeat,second];pairs+=1
        for mode in ['no_dispatch','disabled','foreign']:
            x=struct.unpack('<12288f',images[repeat,'gpu'][256:-256]);y=struct.unpack('<12288f',images[repeat,mode][256:-256]);changes[f'{repeat}:{mode}']=sum(a!=b for a,b in zip(x,y))
        assert changes[f'{repeat}:no_dispatch']==changes[f'{repeat}:disabled']==6144
        assert changes[f'{repeat}:foreign']==12288
        assert images[repeat,'contracts']==images[repeat,'gpu']
        reverse=struct.unpack('<12288f',images[repeat,'reverse'][256:-256]);before=struct.unpack('<12288f',images[repeat,'reverse_no_dispatch'][256:-256]);changes[f'{repeat}:reverse_no_dispatch']=sum(a!=b for a,b in zip(reverse,before));assert changes[f'{repeat}:reverse_no_dispatch']==6144
    for mode in ALL_MODES:assert images[0,mode]==images[1,mode]
    return {'status':'PASS_VERTEX_BINDING_RENDER','signed_terminal_nonoverlapping_hosts':len(proofs),
        'frames':len(proofs),'checked_float_channels':sum(p['checked_float_channels'] for p in proofs),
        'maximum_error':max(p['maximum_error'] for p in proofs),'setter_dispatches':sum(p['dispatches'] for p in proofs),
        'transition_rows_checked':sum(p['vertex_rows_checked'] for p in proofs),
        'native_image_pairs':pairs,'repeat_image_pairs':len(ALL_MODES), 'API_refusals':4,'changed_channels_by_control':changes,
        'static_library_SHA256':bm['static_library_SHA256'],'native_Apple_ICB_ABI':False,'performance_benchmark':False,
        'full_objective_complete':False,'trials':trials}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('root',type=Path);parser.add_argument('--build',type=Path,required=True);parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();result=audit(args.root,args.build);write(args.out,result);print({k:v for k,v in result.items() if k!='trials'})
