#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reject altered copies of finished partial GPU-copy evidence, without GPU work."""
import argparse,json,shutil,subprocess,sys,tempfile
from pathlib import Path

def write(p,x):Path(p).write_text(json.dumps(x,indent=2)+'\n')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--same',type=Path,required=True);p.add_argument('--separate',type=Path,required=True);p.add_argument('--prepare',type=Path,required=True);a=p.parse_args();results={}
 with tempfile.TemporaryDirectory(prefix='partial-gpu-copy-mutations-') as tmp:
  root=Path(tmp).resolve()
  for kind in ('unchanged','wrong-result','guard','descriptor','order','missing-refusal','uncommitted-output','reservation'):
   source=(a.separate if kind in ('order','missing-refusal') else a.prepare if kind=='uncommitted-output' else a.same).resolve();dest=root/kind;shutil.copytree(source,dest);inp=json.loads((dest/'inputs.json').read_text());mfile=dest/'execution/manifest.json';m=json.loads(mfile.read_text());m['arguments']=[str(dest/'assets/partial_buffer_stencil.metallib'),str(dest/'assets/partial_buffer_stencil.json'),str(dest/'outputs'),inp['mode'],str(inp['registry_id']),str(inp['case_index'])];write(mfile,m)
   if kind in ('wrong-result','guard','uncommitted-output'):
    f=dest/'outputs'/('before.b.bin' if kind=='uncommitted-output' else 'after.b.bin');data=bytearray(f.read_bytes());data[0 if kind=='guard' else 64]^=1;f.write_bytes(data)
   elif kind in ('descriptor','order','missing-refusal'):
    f=dest/'results.json';d=json.loads(f.read_text())
    if kind=='descriptor':d['copy_event']['descriptor_pairs'][0]['destination']+=256
    elif kind=='order':d['execution_event']['predecessor_order']['kind']='unordered'
    else:d['ordering_refused']=False
    write(f,d);write(dest/'execution/execution.stdout',d)
   elif kind=='reservation':m['GPU_reservation']['state']='unresolved';write(mfile,m)
   proc=subprocess.run([sys.executable,'-I',str(dest/'src/verify_partial_gpu_copy.py'),str(dest)],capture_output=True,text=True,timeout=120);ok=proc.returncode==0
   if ok!=(kind=='unchanged'):raise ValueError(kind+' unexpected result: '+proc.stderr[-1000:])
   results[kind]='PASS' if ok else 'EXPECTED_REFUSAL'
 print(json.dumps({'status':'PASS','checks':results,'GPU_dispatch':False},sort_keys=True))
if __name__=='__main__':main()
