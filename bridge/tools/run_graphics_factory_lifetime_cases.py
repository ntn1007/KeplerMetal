#!/usr/bin/env python3
"""Qualify frozen graphics/host factories without parallel GTX submissions."""
from pathlib import Path
import argparse,json,subprocess,sys
from verify_graphics_factory_lifetime import verify
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--prefix',required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);history=[];build=a.build.resolve();inp=json.loads((build/'inputs.json').read_text())
reuse={'native_render:cancel':ROOT/'results/graphics-factory-lifetime-native-cancel-20261015','fragment:drop':ROOT/'results/graphics-factory-lifetime-fragment-drop-20261015','tessellation:drop':ROOT/'results/graphics-factory-lifetime-tessellation-drop-20261015'}
first=['native_render:drop','vertex:drop','graphics:drop','native_tess:drop','host_nocopy:drop','host_managed:drop'];allcases=[f+':'+p for f in ['fragment','vertex','graphics','tessellation','host_managed','host_nocopy']for p in ['keep','drop','cancel']]+['native_render:drop','native_render:cancel','native_tess:drop','native_tess:cancel'];order=list(dict.fromkeys([*reuse,*first,*allcases]));assert len(order)==22
for case in order:
 target=reuse.get(case,ROOT/'results'/(a.prefix+'-'+case.replace(':','-')))
 if case in reuse:
  verify(target);assert json.loads((target/'inputs.json').read_text())['executable_SHA256']==inp['executable_SHA256'];history.append({'case':case,'phase':'reuse_existing_terminal_cohort','directory':str(target),'exit_code':0});print(case,'existing proof rechecked',flush=True)
 else:
  for phase,cmd in [('GPU',[sys.executable,ROOT/'tools/run_command_ir_runtime.py','--build',build,'--out',target,'--mode',case]),('CPU',[sys.executable,ROOT/'tools/verify_graphics_factory_lifetime.py',target])]:
   cmd=[str(x)for x in cmd];r=subprocess.run(cmd,capture_output=True,text=True,timeout=75);label=case.replace(':','-')+'-'+phase;(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);history.append({'case':case,'phase':phase,'argv':cmd,'exit_code':r.returncode,'directory':str(target)});(out/'history.json').write_text(json.dumps(history,indent=2)+'\n');assert not r.returncode,(case,phase,r.stderr[-2500:])
  print(case,'GPU+CPU PASS',flush=True)
 (out/'history.json').write_text(json.dumps(history,indent=2)+'\n')
(out/'completion.json').write_text(json.dumps({'status':'PASS','cohorts_including_reused':22,'trials':88,'parallel_GTX_dispatch':False,'Mesa_rebuilt':False,'full_objective_complete':False},indent=2)+'\n')
