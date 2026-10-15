#!/usr/bin/env python3
"""Sequential preparation/GPU/native cohorts; preserve strict numeric failures."""
from pathlib import Path
import argparse,json,subprocess,sys
from verify_fp64_math import verify
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--host',type=Path,required=True);p.add_argument('--cases',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--operations',nargs='+',choices=['add','mul','fma','div','sqrt'],default=['add','mul','fma','div','sqrt']);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();caseDir=a.cases.resolve();caseDir.relative_to(ROOT/'results');records=[]
for op in a.operations:
 for local in [32,128,1024]:
  for mode in ['prepare','execute','native']:
   label=f'{op}-l{local}-{mode}'
   folder=out/label
   argv=[sys.executable,str(ROOT/'tools/run_fp64_math_case.py'),'--host',str(a.host.resolve()),'--plan',str(caseDir/f'{op}-l{local}.plan.json'),'--out',str(folder),'--mode',mode]
   r=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=50);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);assert r.returncode==0,r.stderr[-2500:]
   v=verify(folder);(folder/'independent-verification.json').write_text(json.dumps(v,indent=2)+'\n');records.append({'label':label,'path':str(folder),'verification':{k:x for k,x in v.items() if k!='raw_files_SHA256'},'reused_existing_execution':False})
   (out/'summary.json').write_text(json.dumps({'records':records,'complete':False,'status':'RUNNING','numeric_failures_preserved':True},indent=2)+'\n');print(label,v['status'],v['numeric_mismatches'],v['tag_mismatches'],flush=True)
   if mode=='prepare':assert v['status']=='PASS'
   elif mode=='execute':assert v['tag_mismatches']==0,'Unexpected execution/ABI tags: stop all further GPU launches'
   else:assert v['status']=='PASS_EXPECTED_DIFFERENCE'
status='PASS' if all(r['verification']['status'].startswith('PASS') for r in records) else 'PARTIAL'
(out/'summary.json').write_text(json.dumps({'records':records,'complete':True,'status':status,'numeric_failures_preserved':True,'all_hardware_complete':False},indent=2)+'\n');print(status,flush=True)
