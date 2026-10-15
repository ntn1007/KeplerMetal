#!/usr/bin/env python3
"""Rebuild-client regression recipe; run GPU cohorts sequentially."""
from pathlib import Path
import argparse,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--clients',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();clients=a.clients.resolve();clients.relative_to(ROOT/'results');out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
old=ROOT/'results/gpu-generated-geometry-sdk-clients-20261014';history=json.loads((ROOT/'results/gpu-generated-geometry-nonregression-suite-20261014/commands.json').read_text());assert len(history)==167 and all(c['exit_code']==0 for c in history)
commands=[{'label':c['label'],'argv':[x.replace(str(old),str(clients)).replace('gpu-generated-geometry-regression-','gpu-generated-bindings-regression-')for x in c['argv']]}for c in history]
for mode in ['prepare','select','range','split','completed','copy','no_producer','no_selector','refusals']:
 variant='geometry_refusals'if mode=='refusals'else'geometry'
 target=ROOT/'results'/('gpu-generated-bindings-regression-'+variant+'-'+mode+'-20261014')
 commands.extend([{'label':variant+'-'+mode,'argv':['python3',str(clients/'KeplerMetalSDK/examples/run_gpu_command_geometry.py'),'--build',str(clients/('geometry_refusals-application'if mode=='refusals'else'geometry-application')),'--out',str(target),'--reservation-root',str(ROOT),'--mode',mode]}, {'label':variant+'-'+mode+'-verify','argv':['python3',str(clients/'KeplerMetalSDK/examples'/('verify_gpu_geometry_refusals.py'if mode=='refusals'else'verify_gpu_command_geometry.py')),str(target),'--out',str(target/'independent-verification.json')]}])
assert len(commands)==185
done=[]
for c in commands:
 r=subprocess.run(c['argv'],capture_output=True,text=True);(out/(c['label']+'.stdout')).write_text(r.stdout);(out/(c['label']+'.stderr')).write_text(r.stderr);done.append(dict(c,exit_code=r.returncode));(out/'commands.json').write_text(json.dumps(done,indent=2)+'\n');assert r.returncode==0,(c['label'],r.stderr[-2500:]);print(c['label'],'PASS',flush=True)
(out/'completion.json').write_text(json.dumps({'status':'PASS','commands':185,'GPU_cohorts':129,'parallel_GTX_dispatch':False},indent=2)+'\n')
