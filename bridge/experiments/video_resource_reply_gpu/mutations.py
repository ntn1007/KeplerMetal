#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Challenge copied GPU audit inputs; do not launch GPU work."""
import argparse,json,shutil,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1];sys.path.insert(0,str(BRIDGE/'tools'))
from public_large_scratch import sha,write

def need(x,m):
 if not x:raise ValueError(m)
def main():
 p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--prior',type=Path,required=True);p.add_argument('--runs',type=Path,nargs=6,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();need(a.out.parent.is_dir() and not a.out.exists(),'fresh output');a.out.mkdir();rows=[]
 for name,index in [('gpu-value',3),('guard-value',3),('no-dispatch',2),('missing-match',3),('unfinished',3)]:
  case=a.out/name;case.mkdir();copies=[]
  for i,src in enumerate(a.runs):
   dest=case/str(i);dest.mkdir()
   for n in ('application','execution.json','stdout.json','stderr.log','verification.json'):
    shutil.copyfile(src/n,dest/n)
   if (src/'target.bin').exists():shutil.copyfile(src/'target.bin',dest/'target.bin')
   copies.append(dest)
  target=copies[index];e=json.loads((target/'execution.json').read_text());v=json.loads((target/'verification.json').read_text());r=json.loads((target/'stdout.json').read_text())
  if name in ('gpu-value','guard-value','no-dispatch'):
   data=bytearray((target/'target.bin').read_bytes());data[64 if name!='guard-value' else 0]^=1;(target/'target.bin').write_bytes(data);v['target_capture_sha256']=sha(target/'target.bin');(target/'verification.json').write_text(json.dumps(v,indent=2)+'\n')
  elif name=='missing-match':r['reply_identity']['comparison']['matching_pairs']=0;(target/'stdout.json').write_text(json.dumps(r,indent=2)+'\n');e['stdout_sha256']=sha(target/'stdout.json')
  else:e['reservation']['state']='unresolved'
  (target/'execution.json').write_text(json.dumps(e,indent=2)+'\n');out=case/'audit.json';z=subprocess.run([sys.executable,str(HERE/'audit.py'),'--build',str(a.build),'--prior',str(a.prior),'--runs',*(str(x) for x in copies),'--out',str(out)],capture_output=True,timeout=120);need(z.returncode!=0 and not out.exists(),'mutation accepted '+name);rows.append({'mutation':name,'refused':True})
 result={'status':'PASS_REPLY_GPU_AUDIT_MUTATIONS','mutations':rows,'source_audit_sha256':sha(HERE/'audit.py'),'script_sha256':sha(Path(__file__)),'native_calls':0,'gpu_execution':False};write(a.out/'validation.json',result);print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
