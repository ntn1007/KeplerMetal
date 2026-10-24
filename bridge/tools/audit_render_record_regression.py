#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck legacy render and compute IRv2 on the render-root runtime."""
from pathlib import Path
import argparse
import json
import subprocess
import sys
from public_large_scratch import read,sha,write
from verify_air_reset_render import verify,MODES

COMPUTE=(('library','basic','0:0:0'),('library','copy','2:8:5'),
    ('library','encoder_reuse','1:1:2'),('library_reusable','basic','0:0:0'),
    ('library_reusable','delayed_consumer','2:8:5'),('library_reusable','stale_root','1:1:2'),
    ('library_contracts','pointer','0:0:0'),('library_contracts','reusable','0:0:0'),
    ('contracts','inspect','0:0:0'))


def audit(root):
    root=Path(root).resolve();rows=[];intervals=[];render=[];compute=[]
    rb=read(root/'legacy-render-build/inputs.json');cb=read(root/'compute-regression-build/inputs.json')
    runtime=rb['static_library_SHA256'];assert runtime==cb['static_library_SHA256']
    for family,key in [('render',mode)for mode in MODES]+[('compute',str(i))for i in range(len(COMPUTE))]:
        p=root/'regression'/family/key;m=read(p/'execution/manifest.json');inp=read(p/'inputs.json')
        assert inp['static_library_SHA256']==runtime
        assert m['exit_code']==0 and not m['SIGKILL_requested']and not m['authoritative_ps_status']
        assert m['GPU_reservation']['state']=='terminal'and not m['system_modified']
        assert sha(p/'application')==m['original_binary_sha256']
        assert sha(p/'execution/application')==m['signed_binary_sha256']
        intervals.append((m['started_at'],m['completed_at']))
        if family=='render':
            proof=verify(p);assert not inp['render_argument_encoders']
            assert inp==dict(rb,mode=key,driver_SHA256=inp['driver_SHA256'],source_build_inputs_SHA256=sha(root/'legacy-render-build/inputs.json'))
            expected=dict(proof,PID=m['pid'],static_library_SHA256=runtime);render.append(proof)
        else:
            kind,mode,route=COMPUTE[int(key)];assert (inp['kind'],inp['mode'],inp['library_route'])==(kind,mode,route)
            assert inp['source_build_inputs_SHA256']==sha(root/'compute-regression-build/inputs.json')
            for field in cb:assert inp[field]==cb[field],field
            module='verify_native_library_contracts'if kind=='library_contracts'else'verify_native_function_contracts'if kind=='contracts'else'verify_command_ir_dataflow'
            code='import sys,json;sys.path.insert(0,sys.argv[1]);from '+module+' import verify;print(json.dumps(verify(sys.argv[2])))'
            result=subprocess.run([sys.executable,'-I','-c',code,str(p/'oracles'),str(p)],capture_output=True,text=True,check=True)
            assert not result.stderr;proof=json.loads(result.stdout)
            expected=dict(proof,kind=kind,PID=m['pid'],static_library_SHA256=runtime);compute.append(proof)
        assert read(p/'independent-verification.json')==expected
        rows.append(dict(family=family,case=key,PID=m['pid'],**{k:v for k,v in proof.items()if isinstance(v,(str,int,float,bool))}))
    intervals.sort();assert all(a[1]<=b[0]for a,b in zip(intervals,intervals[1:]))
    return dict(status='PASS_RENDER_ROOT_REGRESSION',signed_terminal_nonoverlapping_processes=len(rows),
        render_hosts=len(render),rendered_frames=len(render)*8,
        checked_float_channels=sum(r['checked_float_channels']for r in render),
        reset_dispatches=sum(r['reset_dispatches']for r in render),reset_witness_words=sum(r['reset_witness_words']for r in render),
        compute_hosts=len(compute),exact_uint32_results=sum(r.get('exact_uint32_results',0)for r in compute),
        consumer_invocations=sum(r.get('consumer_invocations',0)for r in compute),
        compute_guard_bytes=sum(r.get('guard_bytes',0)for r in compute),runtime_SHA256=runtime,
        full_objective_complete=False,performance_benchmark=False,cases=rows)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('root',type=Path);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();r=audit(a.root);write(a.out,r);print({k:v for k,v in r.items()if k!='cases'})
