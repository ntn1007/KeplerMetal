#!/usr/bin/env python3
"""Repeat all129 frozen legacy cohorts with freshly linked current-library clients."""
from pathlib import Path
import argparse,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--clients',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--result-prefix',default='command-ir-v2-legacy-regression');a=p.parse_args();assert a.result_prefix.replace('-','').isalnum();clients=a.clients.resolve();clients.relative_to(ROOT/'results');out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
build=json.loads((clients/'client-builds.json').read_text());assert build['status']=='PASS'
old=ROOT/'results/gpu-generated-bindings-sdk-clients-20261014';history=json.loads((ROOT/'results/gpu-generated-bindings-nonregression-suite-20261014/commands.json').read_text());assert len(history)==185 and all(x['exit_code']==0 for x in history)
commands=[]
for c in history:
 args=[x.replace(str(old),str(clients)).replace('gpu-generated-bindings-regression-',a.result_prefix+'-')for x in c['argv']]
 commands.append({'label':c['label'],'argv':args})
assert sum('--build'in x['argv']for x in commands)==129
for c in commands:
 r=subprocess.run(c['argv'],capture_output=True,text=True,timeout=55);(out/(c['label']+'.stdout')).write_text(r.stdout);(out/(c['label']+'.stderr')).write_text(r.stderr);c['exit_code']=r.returncode
 (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert not r.returncode,(c['label'],r.stderr[-2500:]);print(c['label'],'PASS',flush=True)
(out/'completion.json').write_text(json.dumps({'status':'PASS','commands':185,'legacy_GPU_cohorts':129,'parallel_GTX_dispatch':False,'static_library_SHA256':build['static_library_SHA256']},indent=2)+'\n')
