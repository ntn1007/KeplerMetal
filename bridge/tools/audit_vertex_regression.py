#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU-only recheck of indexed-render and compute regression receipts."""
from datetime import datetime
from pathlib import Path
import argparse
import json
import subprocess
import sys
from public_large_scratch import read, sha, write

RENDER=('indexed_gpu','indexed_native','indexed_missing_table','indexed_contracts')
COMPUTE=(('library','basic','0:0:0'),('library','copy','2:8:5'),('library','encoder_reuse','1:1:2'),
 ('library_reusable','basic','0:0:0'),('library_reusable','delayed_consumer','2:8:5'),('library_reusable','stale_root','1:1:2'),
 ('library_contracts','pointer','0:0:0'),('library_contracts','reusable','0:0:0'),('contracts','inspect','0:0:0'))


def audit(root,render_build,compute_build):
    root=Path(root);render_build=Path(render_build);compute_build=Path(compute_build)
    rbuild=read(render_build/'inputs.json');cbuild=read(compute_build/'inputs.json');assert rbuild['static_library_SHA256']==cbuild['static_library_SHA256']
    rows=[];times=[]
    for family,cases,build in [('render',RENDER,render_build),('compute',COMPUTE,compute_build)]:
        for index,case in enumerate(cases):
            p=root/(family+'-'+str(index));inputs=read(p/'inputs.json');receipt=read(p/'execution/manifest.json')
            assert inputs['source_build_inputs_SHA256']==sha(build/'inputs.json') and inputs['static_library_SHA256']==rbuild['static_library_SHA256']
            if family=='render':
                assert inputs['mode']==case;module='verify_indexed_render'
            else:
                kind,mode,route=case;assert (inputs['kind'],inputs['mode'],inputs['library_route'])==(kind,mode,route)
                module='verify_native_library_contracts' if kind=='library_contracts' else 'verify_native_function_contracts' if kind=='contracts' else 'verify_command_ir_dataflow'
            code='import sys,json;sys.path.insert(0,sys.argv[1]);from '+module+' import verify;print(json.dumps(verify(sys.argv[2])))'
            p1=subprocess.run([sys.executable,'-I','-c',code,str(p/'oracles'),str(p)],capture_output=True,text=True);assert p1.returncode==0,(str(p),p1.stderr)
            proof=json.loads(p1.stdout);assert proof['status']=='PASS'
            a=datetime.fromisoformat(receipt['started_at']);b=datetime.fromisoformat(receipt['completed_at']);assert a<=b;times.append((a,b,str(p)))
            rows.append({'family':family,'mode':case if family=='render' else case[1], 'checked_float_channels':proof.get('checked_float_channels',0),
                'exact_uint32_results':proof.get('exact_uint32_results',0),'consumer_invocations':proof.get('consumer_invocations',0),
                'receipt_SHA256':sha(p/'execution/manifest.json'),'result_SHA256':sha(p/'results.json')})
    times.sort()
    for a,b in zip(times,times[1:]):assert a[1]<=b[0],(a,b)
    return {'status':'PASS','signed_terminal_nonoverlapping_hosts':len(rows),'render_hosts':len(RENDER),'compute_hosts':len(COMPUTE),
        'checked_float_channels':sum(r['checked_float_channels'] for r in rows),
        'exact_uint32_results':sum(r['exact_uint32_results'] for r in rows),
        'consumer_invocations':sum(r['consumer_invocations'] for r in rows),
        'static_library_SHA256':rbuild['static_library_SHA256'],'cases':rows}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--render-build',type=Path,required=True);p.add_argument('--compute-build',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();d=audit(args.root,args.render_build,args.compute_build);write(args.out,d);print({k:v for k,v in d.items() if k!='cases'})
