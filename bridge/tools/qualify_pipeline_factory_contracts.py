#!/usr/bin/env python3
"""Serialize six factory variants and the full async-descriptor dataflow matrix."""
from pathlib import Path
import argparse,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--prefix',required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
modes=['no_producer','refusals','barrier','basic','copy','split','no_consumer','no_seed','no_gather','no_finish','bad_parameters','bad_counter','bad_pipeline','bad_buffer3_flag','bad_groups','bad_reserved','encoder_reuse']
cases=[(k,m)for k in range(6)for m in ['basic','barrier','copy']]+[(5,m)for m in modes if m not in ['basic','barrier','copy']];history=[]
for kind,mode in cases:
 target=ROOT/'results'/(a.prefix+f'-k{kind}-'+mode)
 for phase,cmd in [('GPU',[sys.executable,ROOT/'tools/run_command_ir_runtime.py','--build',a.build.resolve(),'--out',target,'--mode',f'{kind}:{mode}']),('CPU',[sys.executable,ROOT/'tools/verify_command_ir_dataflow.py',target])]:
  cmd=[str(x)for x in cmd];r=subprocess.run(cmd,capture_output=True,text=True,timeout=75);(out/(f'k{kind}-'+mode+'-'+phase+'.stdout')).write_text(r.stdout);(out/(f'k{kind}-'+mode+'-'+phase+'.stderr')).write_text(r.stderr);history.append({'factory_kind':kind,'mode':mode,'phase':phase,'argv':cmd,'result':str(target),'exit_code':r.returncode});(out/'history.json').write_text(json.dumps(history,indent=2)+'\n')
  if r.returncode:
   (out/'status.json').write_text(json.dumps({'status':'FAIL','factory_kind':kind,'mode':mode,'phase':phase,'rerun':False},indent=2)+'\n');print(r.stdout,r.stderr,flush=True);sys.exit(r.returncode)
 print(kind,mode,'GPU+CPU PASS',flush=True)
(out/'status.json').write_text(json.dumps({'status':'PASS','cohorts':len(cases),'trials':4*len(cases),'full_objective_complete':False},indent=2)+'\n')
