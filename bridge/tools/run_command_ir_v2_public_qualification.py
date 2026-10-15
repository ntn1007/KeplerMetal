#!/usr/bin/env python3
"""Qualify both IR versions and three-buffer layouts after the legacy sweep."""
from pathlib import Path
import argparse,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
assert json.loads((ROOT/'results/command-ir-v2-full-legacy-suite-20261015/completion.json').read_text())['status']=='PASS'
history=[]
def execute(label,argv):
 r=subprocess.run(argv,capture_output=True,text=True,timeout=55);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);history.append({'label':label,'argv':argv,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(history,indent=2)+'\n');assert not r.returncode,(label,r.stderr[-3000:])
target=str(ROOT/'results/command-ir-v2-API-refusals-20261015');execute('API-refusals-run',['python3',str(ROOT/'tools/run_command_ir_runtime.py'),'--build',str(ROOT/'results/command-ir-v2-API-refusals-build-20261015-02'),'--out',target,'--mode','basic']);execute('API-refusals-verify',['python3',str(ROOT/'tools/verify_command_ir_grid3d.py'),target]);assert json.loads((Path(target)/'results.json').read_text())['API_refusals']==11;print('11 API refusals plus6 positive XYZ trials PASS',flush=True)
modes=['basic','barrier','clear','copy','reset','no_producer','split','bad_flags','bad_tag','bad_pipeline','bad_address','bad_parameters','bad_local','bad_shared','bad_groups','bad_y','bad_threads','bad_stage','bad_error','bad_reserved']
for kind,build,items in [('v1','command-ir-v1-regression-client-build-20261015',modes),('v2-three','command-ir-v2-three-buffer-client-build-20261015',modes),('v2-combined','command-ir-v2-combined-client-build-20261015',modes[:7]+['bad_shared'])]:
 for mode in items:
  target=str(ROOT/'results'/('command-ir-'+kind+'-qualified-'+mode.replace('_','-')+'-20261015'));execute(kind+'-'+mode+'-run',['python3',str(ROOT/'tools/run_command_ir_runtime.py'),'--build',str(ROOT/'results'/build),'--out',target,'--mode',mode]);execute(kind+'-'+mode+'-verify',['python3',str(ROOT/'tools/verify_command_ir_runtime.py'),target]);print(kind,mode,'PASS',flush=True)
(out/'completion.json').write_text(json.dumps({'status':'PASS','v1_regression_trials':60,'v2_three_buffer_trials':60,'v2_combined_shared_trials':24,'API_pre_dispatch_refusals':11,'API_positive_XYZ_trials':6,'static_library_SHA256':'7947557e5a307b8d2f1bb6d43160756b5ab916a071eae3cc5b1f3605c54c58a1'},indent=2)+'\n')
