#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run the existing 52-case reusable and native/NAK regression serially."""
import argparse, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from public_native_msl_commands import REUSABLE_FLOW_MODES,STABLE_FLOW_MODES

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--lab',type=Path,required=True);a=p.parse_args()
 a.out.mkdir();(a.out/'reusable').mkdir();(a.out/'regression').mkdir();(a.out/'logs').mkdir()
 jobs=[('reusable',m,'reusable',m) for m in REUSABLE_FLOW_MODES]
 jobs += [('regression','native-'+m,'dataflow',m) for m in STABLE_FLOW_MODES]
 jobs += [('regression','nak-'+m,'nak',m) for m in ['basic','barrier','copy']]
 jobs += [('regression','records-execute-0','records','execute'),('regression','records-execute-1','records','execute'),('regression','records-no_dispatch','records','no_dispatch')]
 jobs += [('regression','contracts-'+str(i),'contracts','inspect') for i in range(2)]
 jobs += [('regression','nak-function-'+m,'nak_function',m) for m in ['basic','barrier','copy']]
 jobs += [('regression','stable-records-execute-0','stable_records','execute'),('regression','stable-records-execute-1','stable_records','execute'),('regression','stable-records-no_dispatch','stable_records','no_dispatch')]
 assert len(jobs)==52
 for family,name,kind,mode in jobs:
  args=[sys.executable,str(ROOT/'tools/public_native_msl_commands.py'),'run','--build',str(a.base),'--out',str(a.out/family/name),'--reservation-root',str(a.lab),'--kind',kind,'--mode',mode]
  with (a.out/'logs'/f'{family}-{name}.log').open('x') as log:r=subprocess.run(args,stdout=log,stderr=subprocess.STDOUT)
  print(f'{family}/{name}: {"PASS" if r.returncode==0 else "FAIL"}',flush=True)
  if r.returncode:raise SystemExit('Inspect the exact runner and reservation before retrying: '+str(a.out/family/name))
if __name__=='__main__':main()
