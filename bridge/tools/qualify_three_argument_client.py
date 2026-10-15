#!/usr/bin/env python3
"""Run the twenty established n3 modes serially, preserving each fresh cohort."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--prefix',required=True);a=p.parse_args()
out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);history=[]
modes=['basic','barrier','clear','copy','reset','no_producer','split','bad_flags','bad_tag','bad_pipeline','bad_address','bad_parameters','bad_local','bad_shared','bad_groups','bad_y','bad_threads','bad_stage','bad_error','bad_reserved']
for mode in modes:
 target=ROOT/'results'/(a.prefix+'-'+mode)
 for phase,cmd in [('GPU',[sys.executable,ROOT/'tools/run_command_ir_runtime.py','--build',a.build.resolve(),'--out',target,'--mode',mode]),('CPU',[sys.executable,ROOT/'tools/verify_command_ir_runtime.py',target])]:
  cmd=[str(x)for x in cmd];r=subprocess.run(cmd,capture_output=True,text=True,timeout=75);(out/(mode+'-'+phase+'.stdout')).write_text(r.stdout);(out/(mode+'-'+phase+'.stderr')).write_text(r.stderr);history.append({'mode':mode,'phase':phase,'argv':cmd,'exit_code':r.returncode,'result':str(target)});(out/'history.json').write_text(json.dumps(history,indent=2)+'\n')
  if r.returncode:
   (out/'status.json').write_text(json.dumps({'status':'FAIL','mode':mode,'phase':phase,'GPU_cohort_rerun':False},indent=2)+'\n');print(r.stdout,r.stderr,flush=True);sys.exit(r.returncode)
 print(mode,'GPU+CPU PASS',flush=True)
inputs=json.loads((a.build/'inputs.json').read_text())
(out/'status.json').write_text(json.dumps({'status':'PASS','trials':60,'cohorts':20,'static_library_SHA256':inputs['static_library_SHA256'],'inputs_SHA256':hashlib.sha256((a.build/'inputs.json').read_bytes()).hexdigest(),'full_objective_complete':False},indent=2)+'\n')
