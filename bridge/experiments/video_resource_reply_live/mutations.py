#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Challenge archived cohort audit using copied records; never launch GPU work."""
import argparse,json,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1];sys.path.insert(0,str(BRIDGE/'tools'))
from public_large_scratch import sha,write

def need(x,m):
 if not x:raise ValueError(m)
def main():
 p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--runs',type=Path,nargs=6,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();need(a.out.parent.is_dir() and not a.out.exists(),'fresh output required');a.out.mkdir();rows=[]
 for name,index in [('different-pair',3),('wrong-match',3),('extra-reply',3),('raw-export',3),('baseline-target',2),('nonterminal',3)]:
  case=a.out/name;case.mkdir();copies=[]
  for i,source in enumerate(a.runs):
   dest=case/str(i);dest.mkdir()
   for f in ('application','execution.json','stdout.json','stderr.log','verification.json'):shutil.copyfile(source/f,dest/f)
   copies.append(dest)
  target=copies[index];e=json.loads((target/'execution.json').read_text());r=json.loads((target/'stdout.json').read_text())
  if name=='different-pair':r['reply_identity']['comparison']['matching_pairs']=0
  elif name=='wrong-match':r['reply_identity']['comparison']['wrong_value_matches']=1
  elif name=='extra-reply':r['reply_identity']['comparison']['captured_qualified_reply_count']=2
  elif name=='raw-export':r['raw_payload_exported']=True
  elif name=='baseline-target':r['target_created']=True
  else:e['reservation']['state']='unresolved'
  if name!='nonterminal':(target/'stdout.json').write_text(json.dumps(r,indent=2)+'\n');e['stdout_sha256']=sha(target/'stdout.json')
  (target/'execution.json').write_text(json.dumps(e,indent=2)+'\n');out=case/'audit.json';run=subprocess.run([sys.executable,str(HERE/'audit.py'),'--build',str(a.build),'--runs',*(str(x) for x in copies),'--out',str(out)],capture_output=True,text=True,timeout=120);need(run.returncode!=0 and not out.exists(),'mutation accepted '+name);rows.append({'mutation':name,'refused':True})
 result={'status':'PASS_REPLY_LIVE_AUDIT_MUTATIONS','mutations':rows,'source_audit_sha256':sha(HERE/'audit.py'),'script_sha256':sha(Path(__file__)),'native_calls':0,'gpu_execution':False};write(a.out/'validation.json',result);print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
