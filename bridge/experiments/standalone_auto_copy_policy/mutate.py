#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Test refusal of altered public-client and policy evidence offline."""
from pathlib import Path
import argparse,json,shutil,subprocess,sys,tempfile

def write(p,x):Path(p).write_text(json.dumps(x,indent=2)+'\n')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--optin',type=Path,required=True);p.add_argument('--denied',type=Path,required=True);a=p.parse_args();checks={}
 with tempfile.TemporaryDirectory(prefix='standalone-copy-policy-mutations-') as tmp:
  root=Path(tmp).resolve()
  for kind in ('unchanged','wrong-result','guard','descriptor','ordering','preflight','policy-bytes','policy-hash','client-hash','bootstrap','reservation','missing-refusal'):
   source=(a.denied if kind=='missing-refusal' else a.optin).resolve();dest=root/kind;shutil.copytree(source,dest);inp=dest/'inputs.json';i=json.loads(inp.read_text());manifest=dest/'execution/manifest.json';m=json.loads(manifest.read_text());lib='wrong.metallib' if i['mode']=='wrong-library' else 'partial_dual.metallib';m['arguments']=[str(dest/'assets'/lib),str(dest/'outputs'),str(i['scenario']),i['route']];write(manifest,m)
   if kind in ('wrong-result','guard'):
    f=dest/'outputs'/('after.geo.bin' if kind=='guard' else 'after.b.bin');data=bytearray(f.read_bytes());data[0 if kind=='guard' else 64]^=1;f.write_bytes(data)
   elif kind in ('descriptor','ordering','preflight'):
    f=dest/'events.json';events=json.loads(f.read_text())
    if kind=='descriptor':next(x for x in events if x['operation']=='GPU_partial_QMD_copy')['descriptor_pairs'][0]['destination']+=256
    elif kind=='ordering':next(x for x in events if x['operation']=='execute_bounded_partial_range')['predecessor_order'][0]['kind']='unordered'
    else:next(x for x in events if x['operation']=='prepare_automatic_partial_GPU_copy')['whole_range_preflight_before_initialization']=False
    write(f,events)
   elif kind=='policy-bytes':
    f=dest/'assets'/i['policy_name'];f.write_bytes(f.read_bytes()+b' ')
   elif kind in ('policy-hash','client-hash'):
    i['policy_expected_SHA256' if kind=='policy-hash' else 'executable_A_SHA256']='0'*64;write(inp,i)
   elif kind=='bootstrap':
    f=dest/'assets/bootstrap.dylib';data=bytearray(f.read_bytes());data[-1]^=1;f.write_bytes(data)
   elif kind=='reservation':m['GPU_reservation']['state']='unresolved';write(manifest,m)
   elif kind=='missing-refusal':
    f=dest/'execution/execution.stderr';f.write_text(f.read_text().replace('KM_BOOT identity refused','KM_BOOT identity altered'))
   r=subprocess.run([sys.executable,'-I',str(dest/'src/verify.py'),str(dest)],capture_output=True,text=True,timeout=120);ok=r.returncode==0
   if ok!=(kind=='unchanged'):raise ValueError(kind+' unexpected result: '+r.stderr[-1000:])
   checks[kind]='PASS' if ok else 'EXPECTED_REFUSAL'
 print(json.dumps({'status':'PASS','checks':checks,'GPU_dispatch':False},sort_keys=True))
if __name__=='__main__':main()
