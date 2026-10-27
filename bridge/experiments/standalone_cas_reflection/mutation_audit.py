#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check that the standalone CAS oracle refuses targeted corruptions offline."""
import argparse,importlib.util,json,shutil,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('standalone_cas_verify',HERE/'verify.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
def save(p,x):Path(p).write_text(json.dumps(x,indent=2)+'\n')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--optin',type=Path,required=True);a=p.parse_args();source=a.optin.resolve();assert v.verify(source)['mode']=='optin-reflect'
 results={}
 with tempfile.TemporaryDirectory(prefix='kepler-cas-oracle-') as directory:
  root=Path(directory).resolve()
  for scenario in ('unchanged','pixel','duplicate-dispatch','import-proof','factory','trace','reservation'):
   dest=root/scenario;shutil.copytree(source,dest);m=json.loads((dest/'execution/manifest.json').read_text());m['arguments']=[str(dest/'assets/cas_client.metallib'),str(dest/'outputs'),'run'];save(dest/'execution/manifest.json',m)
   if scenario=='pixel':
    r=json.loads((dest/'results.json').read_text());target=dest/'outputs'/r['runs'][0]['file'];b=bytearray(target.read_bytes());b[64]^=1;target.write_bytes(b)
   elif scenario=='duplicate-dispatch':
    r=json.loads((dest/'results.json').read_text());r['runs'][1]=dict(r['runs'][0]);save(dest/'results.json',r);save(dest/'execution/execution.stdout',r)
   elif scenario=='import-proof':
    e=json.loads((dest/'events.json').read_text());e['events'][0]['proof']['constructor_restored']=False;save(dest/'events.json',e)
   elif scenario=='factory':
    e=json.loads((dest/'events.json').read_text());e['events'][0]['factory']='basic';save(dest/'events.json',e)
   elif scenario=='trace':
    t=dest/'execution/execution.stderr';t.write_text(t.read_text().replace('KM_CAS repaired ','KM_CAS missing ',1))
   elif scenario=='reservation':
    m['GPU_reservation']['state']='unresolved';save(dest/'execution/manifest.json',m)
   try:v.verify(dest);passed=True
   except (ValueError,AssertionError,KeyError,FileNotFoundError):passed=False
   assert passed==(scenario=='unchanged'),scenario;results[scenario]='PASS' if passed else 'EXPECTED_REFUSAL'
 print(json.dumps({'status':'PASS','checks':results,'GPU_dispatch':False},indent=2,sort_keys=True))
if __name__=='__main__':main()
