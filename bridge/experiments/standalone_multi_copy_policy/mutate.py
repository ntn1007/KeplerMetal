#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check that the recorded two-copy oracle rejects altered evidence offline."""
import argparse,json,shutil,subprocess,sys,tempfile
from pathlib import Path
def write(p,x):p.write_text(json.dumps(x,indent=2)+'\n')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--optin',type=Path,required=True);a=p.parse_args();checks={}
 with tempfile.TemporaryDirectory(prefix='km-multi-mutations-') as tmp:
  for kind in ('unchanged','second-result','second-guard','second-descriptor','second-ordering','second-preflight','missing-refusal','reservation','bootstrap'):
   dest=(Path(tmp)/kind).resolve();shutil.copytree(a.optin.resolve(),dest);i=json.loads((dest/'inputs.json').read_text());manifest=dest/'execution/manifest.json';m=json.loads(manifest.read_text());m['arguments']=[str(dest/'assets/partial_dual.metallib'),str(dest/'outputs'),str(i['scenario']),i['route']];write(manifest,m)
   if kind in ('second-result','second-guard'):
    f=dest/'outputs'/('after.geo2.bin' if kind=='second-guard' else 'after.b2.bin');data=bytearray(f.read_bytes());data[0 if kind=='second-guard' else 64]^=1;f.write_bytes(data)
   elif kind in ('second-descriptor','second-ordering','second-preflight'):
    f=dest/'events.json';events=json.loads(f.read_text())
    if kind=='second-descriptor':[x for x in events if x['operation']=='GPU_partial_QMD_copy'][-1]['descriptor_pairs'][0]['destination']+=256
    elif kind=='second-ordering':[x for x in events if x['operation']=='execute_bounded_partial_range'][-1]['predecessor_order'][0]['kind']='unordered'
    else:[x for x in events if x['operation']=='prepare_automatic_partial_GPU_copy'][-1]['whole_range_preflight_before_initialization']=False
    write(f,events)
   elif kind=='missing-refusal':
    f=dest/'execution/execution.stderr';f.write_text(f.read_text().replace('KM_BOOT additional copy refused before preflight','KM_BOOT altered refusal'))
   elif kind=='reservation':m['GPU_reservation']['state']='unresolved';write(manifest,m)
   elif kind=='bootstrap':
    f=dest/'assets/bootstrap.dylib';data=bytearray(f.read_bytes());data[-1]^=1;f.write_bytes(data)
   r=subprocess.run([sys.executable,'-I',str(dest/'src/verify.py'),str(dest)],capture_output=True,text=True,timeout=120);ok=r.returncode==0
   if ok!=(kind=='unchanged'):raise ValueError(kind+' unexpected result: '+r.stderr[-1000:])
   checks[kind]='PASS' if ok else 'EXPECTED_REFUSAL'
 print(json.dumps({'status':'PASS','checks':checks,'GPU_dispatch':False},sort_keys=True))
if __name__=='__main__':main()
