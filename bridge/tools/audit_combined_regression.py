#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck legacy indexed, vertex and compute receipts on the dual-root runtime."""
from datetime import datetime
from pathlib import Path
import argparse,json,subprocess,sys
from public_large_scratch import read,sha,write
INDEX=('indexed_gpu','indexed_native','indexed_missing_table','indexed_contracts')
VERTEX=('gpu','native','no_dispatch','foreign','reverse','contracts')
COMPUTE=(('library','basic','0:0:0'),('library','copy','2:8:5'),('library','encoder_reuse','1:1:2'),('library_reusable','basic','0:0:0'),('library_reusable','delayed_consumer','2:8:5'),('library_reusable','stale_root','1:1:2'),('library_contracts','pointer','0:0:0'),('library_contracts','reusable','0:0:0'),('contracts','inspect','0:0:0'))


def audit(root,index_build,vertex_build,compute_build):
 root=Path(root);builds=[Path(index_build),Path(vertex_build),Path(compute_build)];metadata=[read(p/'inputs.json')for p in builds];assert len({m['static_library_SHA256']for m in metadata})==1
 rows=[];times=[]
 for family,cases,build in [('index',INDEX,builds[0]),('vertex',VERTEX,builds[1]),('compute',COMPUTE,builds[2])]:
  for i,case in enumerate(cases):
   p=root/(family+'-'+str(i));inputs=read(p/'inputs.json');receipt=read(p/'execution/manifest.json');assert inputs['source_build_inputs_SHA256']==sha(build/'inputs.json') and inputs['static_library_SHA256']==metadata[0]['static_library_SHA256']
   if family=='compute':
    kind,mode,route=case;assert(inputs['kind'],inputs['mode'],inputs['library_route'])==(kind,mode,route);module='verify_native_library_contracts'if kind=='library_contracts'else'verify_native_function_contracts'if kind=='contracts'else'verify_command_ir_dataflow'
   else:
    assert inputs['mode']==case;mode=case;module='verify_indexed_render'if family=='index'else'verify_vertex_binding_render'
   code='import sys,json;sys.path.insert(0,sys.argv[1]);from '+module+' import verify;print(json.dumps(verify(sys.argv[2])))';check=subprocess.run([sys.executable,'-I','-c',code,str(p/'oracles'),str(p)],capture_output=True,text=True);assert check.returncode==0,(str(p),check.stderr)
   proof=json.loads(check.stdout);assert proof['status']=='PASS';a=datetime.fromisoformat(receipt['started_at']);b=datetime.fromisoformat(receipt['completed_at']);assert a<=b;times.append((a,b,str(p)))
   rows.append({'family':family,'mode':mode,'checked_float_channels':proof.get('checked_float_channels',0),'exact_uint32_results':proof.get('exact_uint32_results',0),'consumer_invocations':proof.get('consumer_invocations',0),'receipt_SHA256':sha(p/'execution/manifest.json'),'result_SHA256':sha(p/'results.json')})
 times.sort()
 for a,b in zip(times,times[1:]):assert a[1]<=b[0],(a,b)
 return {'status':'PASS','signed_terminal_nonoverlapping_hosts':len(rows),'indexed_hosts':len(INDEX),'vertex_hosts':len(VERTEX),'compute_hosts':len(COMPUTE),'checked_float_channels':sum(x['checked_float_channels']for x in rows),'exact_uint32_results':sum(x['exact_uint32_results']for x in rows),'consumer_invocations':sum(x['consumer_invocations']for x in rows),'static_library_SHA256':metadata[0]['static_library_SHA256'],'cases':rows}


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path)
 for name in ['index-build','vertex-build','compute-build','out']:p.add_argument('--'+name,type=Path,required=True)
 a=p.parse_args();d=audit(a.root,a.index_build,a.vertex_build,a.compute_build);write(a.out,d);print({k:v for k,v in d.items()if k!='cases'})
