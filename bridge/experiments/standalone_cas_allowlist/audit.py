#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck allowlist, source provenance and numerical CAS results."""
import argparse,copy,hashlib,importlib.util,json,subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('cas_allowlist_verify',HERE/'verify.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(v,s):
 if not v:raise ValueError(s)
def reflection_equal(rows):return len(rows)==6 and all(x==rows[0] for x in rows[1:]) and rows[0][2]['reflection_present'] and len(rows[0][2]['arguments'])==3
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--runs',type=Path,nargs='+',required=True);a=p.parse_args();b=a.build.resolve();runs=[p.resolve() for p in a.runs];need(len(runs)==len(set(runs))==12,'Twelve distinct hosts required');i=read(b/'inputs.json')
 for n,h in i['frozen'].items():need(sha(b/n)==h,'Build input differs '+n)
 for n in ('client.mm','bootstrap.mm','verify.py','experiment.py'):need(sha(HERE/n)==i['frozen']['src/'+n],'Source differs '+n)
 ah,bh=i['executable_SHA256'],i['executable_B_SHA256'];need(ah!=bh and sha(b/'application')==ah and sha(b/'application-b')==bh,'Client hashes differ')
 need(read(b/'assets/policy-a.json')=={'version':1,'allowed_clients':[ah]} and read(b/'assets/policy-ab.json')=={'version':1,'allowed_clients':[ah,bh]},'Policy membership differs')
 for binary in ('application','application-b'):
  path=b/binary;subprocess.run(['codesign','--verify','--strict',str(path)],check=True,capture_output=True);symbols=subprocess.run(['nm','-u',str(path)],check=True,capture_output=True,text=True).stdout;need('Kepler' not in symbols and 'KPCreate' not in symbols,'Client imports project API')
 rows=[];pids=set();intervals=[];refs=[]
 for path in runs:
  inp=read(path/'inputs.json');m=read(path/'execution/manifest.json');mode=inp['mode'];need(inp['build_inputs_SHA256']==sha(b/'inputs.json'),'Run build differs')
  expected_tag='B' if mode in ('native-b','optin-b','denied-b') else 'A';expected_policy='policy-ab.json' if mode=='optin-b' else 'policy-a.json'
  need(inp['client_tag']==expected_tag and inp['policy_name']==expected_policy and inp['policy_expected_SHA256']==sha(b/'assets'/expected_policy),'Client or policy selection differs')
  expected=sha(b/'assets/wrong-application') if mode=='wrong-client' else bh if inp['client_tag']=='B' else ah
  need(inp['application_SHA256']==expected and (m['signed_binary_sha256']!=ah if mode=='wrong-client' else m['signed_binary_sha256']==expected),'Signed client differs')
  for n,h in inp['frozen'].items():need(h==i['frozen'][n] and sha(path/n)==h,'Run input differs '+n)
  for n,h in inp['assets_SHA256'].items():
   mutated=(mode=='wrong-cert' and n==read(path/'assets/client-manifest.json')['profiles'][0]['certificate']) or (mode=='wrong-policy' and n=='policy-a.json')
   need((h!=i['frozen']['assets/'+n]) if mutated else (h==i['frozen']['assets/'+n]),'Asset differs '+n)
  result=v.verify(path);need(result==read(path/'verification.json'),'Oracle differs');rows.append(result)
  need(m['pid'] not in pids,'Duplicate PID');pids.add(m['pid']);intervals.append((datetime.fromisoformat(m['started_at']),datetime.fromisoformat(m['completed_at'])))
  if mode in ('native-a','native-b','optin-a','optin-b'):refs.append(read(path/'results.json')['proofs'])
 need(Counter(x['mode'] for x in rows)==Counter({'native-a':1,'native-b':1,'optin-a':2,'optin-b':2,'denied-b':1,'wrong-policy':1,'wrong-library':1,'wrong-descriptor':1,'wrong-client':1,'wrong-cert':1}),'Mode coverage differs')
 intervals.sort();need(all(x<=y for x,y in intervals) and all(x[1]<=y[0] for x,y in zip(intervals,intervals[1:])),'Overlapping hosts')
 need(reflection_equal(refs),'Selected reflection differs');mut=copy.deepcopy(refs);mut[1][2]['arguments'][0]['index']+=1;need(not reflection_equal(mut),'Changed reflection accepted')
 nat=[r for r in rows if r['mode'].startswith('native-')];opt=[r for r in rows if r['mode'].startswith('optin-')]
 print(json.dumps({'status':'PASS','host_processes':len(rows),'nonoverlapping':True,'client_A_SHA256':ah,'client_B_SHA256':bh,'policy_A_SHA256':sha(b/'assets/policy-a.json'),'policy_AB_SHA256':sha(b/'assets/policy-ab.json'),'bootstrap_SHA256':i['frozen']['assets/bootstrap.dylib'],'archive_SHA256':i['archive_SHA256'],'native_defect_words':sum(r['expected_native_defect_words'] for r in nat),'native_dispatches':sum(r['user_GPU_dispatches'] for r in nat),'corrected_and_control_CAS_operations':sum(r['correct_CAS_operations'] for r in opt),'optin_dispatches':sum(r['user_GPU_dispatches'] for r in opt),'selected_reflection_equal':True,'mutated_reflection_rejected':True,'negative_controls':['denied-b','wrong-policy','wrong-library','wrong-descriptor','wrong-client','wrong-cert'],'client_imports_project_symbols':False,'installed_driver_modified':False,'scope':'Two builds of one purpose-built client; explicit local policy and fixed certified library, not general or transparent application support'},indent=2,sort_keys=True))
if __name__=='__main__':main()
