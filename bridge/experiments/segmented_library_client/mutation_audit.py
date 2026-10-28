#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise offline auditor refusal using copies of finished receipts."""
import argparse, hashlib, json, shutil, subprocess, sys, tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--foreign',type=Path,required=True);p.add_argument('--native',type=Path,nargs=2,required=True);p.add_argument('--optin',type=Path,nargs=2,required=True);a=p.parse_args()
 build=a.build.resolve();sources=[a.foreign.resolve(),*[x.resolve() for x in a.native],*[x.resolve() for x in a.optin]];results={}
 with tempfile.TemporaryDirectory(prefix='segmented-cas-audit-') as tmp:
  root=Path(tmp).resolve()
  for scenario in ('unchanged','output','guard','data-trace','reservation'):
   case=root/scenario;case.mkdir();copies=[]
   for index,src in enumerate(sources):
    dest=case/f'receipt-{index}';shutil.copytree(src,dest);shutil.copytree(Path(str(src)+'-output'),Path(str(dest)+'-output'));copies.append(dest)
    mpath=dest/'manifest.json';m=json.loads(mpath.read_text());args=[str(build/'assets'/('wrong.metallib' if index==0 else 'cas_client.metallib')),str(Path(str(dest)+'-output')),'construct' if index==0 else 'run'];m['arguments_SHA256']=hashlib.sha256(json.dumps(args,ensure_ascii=False,separators=(',',':')).encode()).hexdigest();mpath.write_text(json.dumps(m,indent=2)+'\n')
   if scenario in ('output','guard'):
    out=Path(str(copies[3])+'-output')/'case-33-0-0.bin';data=bytearray(out.read_bytes());data[64 if scenario=='output' else 0]^=1;out.write_bytes(data)
   elif scenario=='data-trace':
    t=copies[3]/'execution.stderr';s=t.read_text();assert s.count('KM_CAS data library matched')==1;t.write_text(s.replace('KM_CAS data library matched','KM_CAS missing data witness',1))
   elif scenario=='reservation':
    f=copies[3]/'manifest.json';m=json.loads(f.read_text());m['GPU_reservation']['state']='unresolved';f.write_text(json.dumps(m,indent=2)+'\n')
   cmd=[sys.executable,str(HERE/'audit.py'),'--build',str(build),'--foreign',str(copies[0]),'--native',str(copies[1]),str(copies[2]),'--optin',str(copies[3]),str(copies[4]),'--out',str(case/'audit.json')]
   proc=subprocess.run(cmd,capture_output=True,text=True,timeout=180);ok=proc.returncode==0
   if ok!=(scenario=='unchanged'):raise ValueError(f'{scenario} unexpected outcome: {proc.stderr[-1000:]}')
   results[scenario]='PASS' if ok else 'EXPECTED_REFUSAL'
 print(json.dumps({'status':'PASS','checks':results,'GPU_dispatch':False},sort_keys=True))
if __name__=='__main__':main()
