#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck runtime-owned pipeline roots and same-runtime GPU regressions."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess
import sys

INTEGRATED=('gpu','native','no_dispatch','no_dispatch_native','reverse','reverse_native',
            'reverse_no_dispatch','reverse_no_dispatch_native','contracts')
VERTEX=('gpu','native','foreign','contracts')
COMBINED=('gpu','native','foreign_vertex','missing_index','reverse','reverse_native')


def audit(root):
    root=Path(root);entries=[];integrated={};regressions={};reflection={};compute={};api_refusals=0;libraries=set()
    runs=[]
    for cohort in (1,2):
        for mode in INTEGRATED:runs.append((f'integrated-{mode}-{cohort:02}','verify_pipeline_binding_integrated',integrated,(cohort,mode)))
    for prefix,modes,module in (('regression-vertex',VERTEX,'verify_vertex_binding_render'),('regression-combined',COMBINED,'verify_combined_index_vertex')):
        for mode in modes:runs.append((f'{prefix}-{mode}',module,regressions,(prefix,mode)))
    for mode in ('contracts','reverse'):runs.append((f'reflection-{mode}','verify_pipeline_binding_integrated',reflection,mode))
    for name,module in (('compute-library-basic','verify_command_ir_dataflow'),('compute-library_reusable-stale_root','verify_command_ir_dataflow'),('compute-library_contracts-pointer','verify_native_library_contracts')):
        runs.append((name,module,compute,name))
    for name,module,group,key in runs:
        path=root/name
        code='import sys,json;sys.path.insert(0,sys.argv[1]);from '+module+' import verify;print(json.dumps(verify(sys.argv[2])))'
        p=subprocess.run([sys.executable,'-I','-c',code,str(path/'oracles'),str(path)],capture_output=True,text=True,check=True)
        proof=json.loads(p.stdout);assert proof['status']=='PASS';group[key]=proof
        if module=='verify_pipeline_binding_integrated':api_refusals+=len(json.loads((path/'results.json').read_text())['refusals'])
        libraries.add(json.loads((path/'inputs.json').read_text())['static_library_SHA256'])
        receipt=json.loads((path/'execution/manifest.json').read_text());start=datetime.fromisoformat(receipt['started_at']);end=datetime.fromisoformat(receipt['completed_at'])
        assert start<=end;entries.append((start,end,receipt['pid'],name))
    entries.sort()
    for first,second in zip(entries,entries[1:]):assert first[1]<=second[0],(first,second)
    assert len({item[2] for item in entries})==len(entries)
    assert len(libraries)==1
    pairs=(('gpu','native'),('no_dispatch','no_dispatch_native'),('reverse','reverse_native'),('reverse_no_dispatch','reverse_no_dispatch_native'))
    for cohort in (1,2):
        for a,b in pairs:
            assert (root/f'integrated-{a}-{cohort:02}/outputs/image.bin').read_bytes()==(root/f'integrated-{b}-{cohort:02}/outputs/image.bin').read_bytes(),(cohort,a,b)
        assert (root/f'integrated-contracts-{cohort:02}/outputs/image.bin').read_bytes()==(root/f'integrated-gpu-{cohort:02}/outputs/image.bin').read_bytes()
    for mode in INTEGRATED:
        assert (root/f'integrated-{mode}-01/outputs/image.bin').read_bytes()==(root/f'integrated-{mode}-02/outputs/image.bin').read_bytes(),mode
    assert (root/'integrated-gpu-01/outputs/image.bin').read_bytes()!=(root/'integrated-no_dispatch-01/outputs/image.bin').read_bytes()
    for prefix in ('regression-vertex','regression-combined'):
        assert (root/f'{prefix}-gpu/outputs/image.bin').read_bytes()==(root/f'{prefix}-native/outputs/image.bin').read_bytes()
    return {'status':'PASS','integrated_hosts':len(integrated),'regression_hosts':len(regressions),
            'reflection_and_lifetime_hosts':len(reflection),'compute_regression_hosts':len(compute),
            'integrated_float_channels':sum(x['checked_float_channels'] for x in integrated.values()),
            'integrated_dispatches':sum(x['dispatches'] for x in integrated.values()),
            'regression_float_channels':sum(x['checked_float_channels'] for x in regressions.values()),
            'compute_exact_uint32_results':sum(x.get('exact_uint32_results',0) for x in compute.values()),
            'integrated_native_pairs':len(pairs)*2,'repeat_image_pairs':len(INTEGRATED),
            'expected_api_refusals':api_refusals,'serialized_hosts':len(entries),
            'static_library_SHA256':next(iter(libraries)),
            'maximum_cpu_error':max(x['maximum_error'] for x in integrated.values()),
            'scope':'explicit per-process adapter; not transparent Metal support'}


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    assert not a.out.exists();a.out.write_text(json.dumps(audit(a.root),indent=2)+'\n');print(a.out)
