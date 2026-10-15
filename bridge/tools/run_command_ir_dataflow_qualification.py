#!/usr/bin/env python3
"""Serialize bounded GTX cohorts and stop on the first CPU-oracle failure."""
from pathlib import Path
import argparse,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--prefix',required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);history=[]
modes=['no_producer','refusals','barrier','basic','copy','split','no_consumer','no_seed','no_gather','no_finish','bad_parameters','bad_counter','bad_pipeline','bad_buffer3_flag','bad_groups','bad_reserved']
for mode in modes:
 result=ROOT/'results'/(a.prefix+'-'+mode)
 for label,cmd in [('GPU',[sys.executable,ROOT/'tools/run_command_ir_runtime.py','--build',a.build.resolve(),'--out',result,'--mode',mode]),('CPU',[sys.executable,ROOT/'tools/verify_command_ir_dataflow.py',result])]:
  cmd=[str(x)for x in cmd];r=subprocess.run(cmd,capture_output=True,text=True,timeout=75);(out/(mode+'-'+label+'.stdout')).write_text(r.stdout);(out/(mode+'-'+label+'.stderr')).write_text(r.stderr);history.append({'mode':mode,'phase':label,'argv':cmd,'exit_code':r.returncode,'result':str(result)});(out/'history.json').write_text(json.dumps(history,indent=2)+'\n')
  if r.returncode:
   (out/'status.json').write_text(json.dumps({'status':'FAIL','mode':mode,'phase':label,'GPU_cohort_rerun':False},indent=2)+'\n');print(r.stdout,r.stderr,flush=True);sys.exit(r.returncode)
 print(mode,'GPU+CPU PASS',flush=True)
(out/'status.json').write_text(json.dumps({'status':'PASS','cohorts':len(modes),'trials':4*len(modes),'full_objective_complete':False},indent=2)+'\n')
