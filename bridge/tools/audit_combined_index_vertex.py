#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck signed combined render receipts, images and negative controls."""
from pathlib import Path
from datetime import datetime
import argparse
import json
import struct
import subprocess
import sys
from public_large_scratch import read,sha,write
from verify_combined_index_vertex import MODES


def audit(root,build):
 root=Path(root);build=Path(build);bm=read(build/'inputs.json');trials=[];times=[];images={};proofs=[]
 for repeat in range(2):
  for mode in MODES:
   p=root/str(repeat)/mode;inputs=read(p/'inputs.json');receipt=read(p/'execution/manifest.json')
   assert inputs['source_build_inputs_SHA256']==sha(build/'inputs.json') and inputs['static_library_SHA256']==bm['static_library_SHA256']
   code='import sys,json;sys.path.insert(0,sys.argv[1]);from verify_combined_index_vertex import verify;print(json.dumps(verify(sys.argv[2])))'
   check=subprocess.run([sys.executable,'-I','-c',code,str(p/'oracles'),str(p)],capture_output=True,text=True);assert check.returncode==0,(str(p),check.stderr)
   proof=json.loads(check.stdout);assert proof['status']=='PASS' and proof['mode']==mode
   images[repeat,mode]=(p/'outputs/image.bin').read_bytes();a=datetime.fromisoformat(receipt['started_at']);b=datetime.fromisoformat(receipt['completed_at']);assert a<=b;times.append((a,b,repeat,mode))
   trials.append({'repeat':repeat,'mode':mode,'receipt_SHA256':sha(p/'execution/manifest.json'),'result_SHA256':sha(p/'results.json'),'image_SHA256':sha(p/'outputs/image.bin')});proofs.append(proof)
 times.sort()
 for a,b in zip(times,times[1:]):assert a[1]<=b[0],(a,b)
 pairs=0;changes={}
 for repeat in range(2):
  for mode in ('gpu','no_dispatch','disabled','draw_first','reset','foreign_vertex','foreign_index','missing_vertex','missing_index','reverse'):
   native='native' if mode=='gpu' else mode+'_native';assert images[repeat,mode]==images[repeat,native];pairs+=1
  assert images[repeat,'draw_first']==images[repeat,'gpu']
  expected={'no_dispatch':6144,'disabled':6144,'foreign_vertex':12288,'foreign_index':12288,'missing_vertex':12288,'missing_index':12288,'reset':12288,'reverse':6144}
  a=struct.unpack('<12288f',images[repeat,'gpu'][256:-256])
  for mode,count in expected.items():
   b=struct.unpack('<12288f',images[repeat,mode][256:-256]);n=sum(x!=y for x,y in zip(a,b));assert n==count,(repeat,mode,n);changes[f'{repeat}:{mode}']=n
 for mode in MODES:assert images[0,mode]==images[1,mode]
 return {'status':'PASS_COMBINED_INDEX_VERTEX','signed_terminal_nonoverlapping_hosts':len(proofs),'frames':len(proofs),'checked_float_channels':sum(p['checked_float_channels'] for p in proofs),'maximum_error':max(p['maximum_error']for p in proofs),'producer_dispatches':sum(p['producer_dispatches']for p in proofs),'index_rows_checked':sum(p['index_rows_checked']for p in proofs),'vertex_rows_checked':sum(p['vertex_rows_checked']for p in proofs),'native_image_pairs':pairs,'repeat_image_pairs':len(MODES),'changed_channels_by_control':changes,'static_library_SHA256':bm['static_library_SHA256'],'native_Apple_ICB_ABI':False,'performance_benchmark':False,'full_objective_complete':False,'trials':trials}


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=audit(a.root,a.build);write(a.out,d);print({k:v for k,v in d.items()if k!='trials'})
