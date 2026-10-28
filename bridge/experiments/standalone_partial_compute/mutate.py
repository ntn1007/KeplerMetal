#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Alter preserved evidence to test that the standalone CPU oracle refuses it."""
from pathlib import Path
import argparse,json,shutil,subprocess,sys,tempfile

def write(p,x):Path(p).write_text(json.dumps(x,indent=2)+'\n')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--auto',type=Path,required=True);p.add_argument('--wrong-client',type=Path,required=True);a=p.parse_args();checks={}
 with tempfile.TemporaryDirectory(prefix='standalone-partial-mutations-') as tmp:
  root=Path(tmp).resolve()
  for kind in ('unchanged','wrong-result','guard','command-status','factory-event','native-profile','reservation','missing-refusal'):
   source=(a.wrong_client if kind=='missing-refusal' else a.auto).resolve();dest=root/kind;shutil.copytree(source,dest);i=json.loads((dest/'inputs.json').read_text());manifest=dest/'execution/manifest.json';m=json.loads(manifest.read_text());library='wrong.metallib' if i['mode']=='wrong-library' else 'partial_dual.metallib';m['arguments']=[str(dest/'assets'/library),str(dest/'outputs'),str(i['scenario'])];write(manifest,m)
   if kind in ('wrong-result','guard'):
    f=dest/'outputs'/('after.geo.bin' if kind=='guard' else 'after.b.bin');data=bytearray(f.read_bytes());data[0 if kind=='guard' else 64]^=1;f.write_bytes(data)
   elif kind=='command-status':
    f=dest/'execution/execution.stdout';data=json.loads(f.read_text());data['command_status']=0;write(f,data)
   elif kind in ('factory-event','native-profile'):
    f=dest/'events.json';events=json.loads(f.read_text())
    if kind=='factory-event':events=[e for e in events if e['operation']!='automatic_compute_encoder']
    else:next(e for e in events if e['operation']=='execute_bounded_partial_range')['evidence']['owner_original_profiles'][0]['native_register_count']+=1
    write(f,events)
   elif kind=='reservation':m['GPU_reservation']['state']='unresolved';write(manifest,m)
   elif kind=='missing-refusal':
    f=dest/'execution/execution.stderr';f.write_text(f.read_text().replace('KM_BOOT identity refused','KM_BOOT identity altered'))
   result=subprocess.run([sys.executable,'-I',str(dest/'src/verify.py'),str(dest)],capture_output=True,text=True,timeout=120);ok=result.returncode==0
   if ok!=(kind=='unchanged'):raise ValueError(kind+' unexpected result: '+result.stderr[-1000:])
   checks[kind]='PASS' if ok else 'EXPECTED_REFUSAL'
 print(json.dumps({'status':'PASS','checks':checks,'GPU_dispatch':False},sort_keys=True))
if __name__=='__main__':main()
