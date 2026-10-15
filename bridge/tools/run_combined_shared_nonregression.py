#!/usr/bin/env python3
"""Rebuilt SDK clients, sequentially, with the completed prior suite as recipe."""
from pathlib import Path
import argparse
import json
import subprocess

ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--clients',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
clients=a.clients.resolve();clients.relative_to(ROOT/'results');out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
old=ROOT/'results/resident-dynamic-sdk-clients-20261014'
h=json.loads((ROOT/'results/resident-dynamic-nonregression-suite-20261014/commands.json').read_text());last={c['label']:c for c in h}
assert len(last)==105 and all(c['exit_code']==0 for c in last.values())
commands=[]
for c in last.values():
    commands.append({'label':c['label'],'argv':[x.replace(str(old),str(clients)).replace('resident-dynamic-regression-','resident-combined-shared-regression-')for x in c['argv']]})
for variant,modes,verifier in [('dynamic',['prepare','chain','range','chain_completed','range_completed','no_second'],'verify_dynamic_resident_copy.py'),('dynamic_bounds',['prepare_bound','prepare_private','copy_bound','owner_bound','execute_owner_bound'],'verify_dynamic_resident_bounds.py')]:
    for mode in modes:
        target=ROOT/'results'/('resident-combined-shared-regression-'+variant+'-'+mode+'-20261014')
        commands.extend([{'label':variant+'-'+mode,'argv':['python3',str(clients/'KeplerMetalSDK/examples/run_dynamic_resident_copy.py'),'--build',str(clients/(variant+'-application')),'--out',str(target),'--reservation-root',str(ROOT),'--mode',mode]},
                         {'label':variant+'-'+mode+'-verify','argv':['python3',str(clients/'KeplerMetalSDK/examples'/verifier),str(target),'--out',str(target/'independent-verification.json')]}])
assert len(commands)==127
history=[]
for c in commands:
    r=subprocess.run(c['argv'],capture_output=True,text=True)
    (out/(c['label']+'.stdout')).write_text(r.stdout);(out/(c['label']+'.stderr')).write_text(r.stderr)
    history.append(dict(c,exit_code=r.returncode));(out/'commands.json').write_text(json.dumps(history,indent=2)+'\n')
    assert r.returncode==0,(c['label'],r.stderr[-2500:])
    print(c['label'],'PASS',flush=True)
(out/'completion.json').write_text(json.dumps({'status':'PASS','commands':127,'GPU_cohorts':100,'parallel_GTX_dispatch':False},indent=2)+'\n')
