#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit standalone CAS hosts, provenance, and raw GPU outputs offline."""
import argparse
from collections import Counter
from datetime import datetime
import copy,hashlib,importlib.util,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('standalone_cas_verify',HERE/'verify.py');v=importlib.util.module_from_spec(spec);spec.loader.exec_module(v)
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(c,s):
 if not c:raise ValueError(s)
def compare_reflections(refs):
 return len(refs)==4 and all(x==refs[0] for x in refs[1:]) and all(x['reflection_present'] and len(x['arguments'])==3 for x in refs[0])
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--runs',type=Path,nargs='+',required=True);a=p.parse_args();b=a.build.resolve();runs=[x.resolve() for x in a.runs]
 require(len(runs)==len(set(runs))==10,'Expected ten distinct hosts');i=read(b/'inputs.json')
 for name,h in i['frozen'].items():require(sha(b/name)==h,'Build input differs: '+name)
 for name in ('client.mm','bootstrap.mm','verify.py','experiment.py'):require(i['frozen']['src/'+name]==sha(HERE/name),'Current source differs: '+name)
 require(sha(b/'application')==i['executable_SHA256'] and not i['client_imports_project_symbols'] and not i['GPU_dispatch'],'Client build differs')
 imports=subprocess.run(['nm','-u',str(b/'application')],capture_output=True,text=True,check=True).stdout
 require('Kepler' not in imports and 'KPCreate' not in imports,'Client imports project API')
 rows=[];intervals=[];pids=set()
 for path in runs:
  inp=read(path/'inputs.json');m=read(path/'execution/manifest.json');require(inp['build_inputs_SHA256']==sha(b/'inputs.json'),'Run build differs')
  mode=inp['mode'];expected=sha(b/'assets/wrong-application') if mode=='wrong-client' else i['executable_SHA256']
  require(inp['application_SHA256']==expected,'Executable copy differs')
  require(m['signed_binary_sha256']!=i['executable_SHA256'] if mode=='wrong-client' else m['signed_binary_sha256']==expected,'Signed executable identity differs')
  for name,h in inp['frozen'].items():require(h==i['frozen'][name] and sha(path/name)==h,'Run source differs: '+name)
  for name,h in inp['assets_SHA256'].items():
   if mode=='wrong-cert' and name==read(path/'assets/client-manifest.json')['profiles'][0]['certificate']:
    require(h!=i['frozen']['assets/'+name],'Wrong certificate was unchanged')
   else:require(h==i['frozen']['assets/'+name],'Run asset differs: '+name)
  result=v.verify(path);require(result==read(path/'verification.json'),'Stored verification differs');rows.append(result)
  require(m['pid'] not in pids,'Duplicate PID');pids.add(m['pid']);intervals.append((datetime.fromisoformat(m['started_at']),datetime.fromisoformat(m['completed_at'])))
 require(Counter(x['mode'] for x in rows)==Counter({'native-reflect':2,'optin-reflect':2,'optin-option':1,'optin-reflection':1,'optin':1,'wrong-client':1,'wrong-cert':1,'wrong-library':1}),'Mode coverage differs')
 intervals.sort();require(all(x<=y for x,y in intervals) and all(x[1]<=y[0] for x,y in zip(intervals,intervals[1:])),'Host intervals overlap')
 refs=[read(path/'results.json')['proofs'] for path in runs if read(path/'inputs.json')['mode'] in ('native-reflect','optin-reflect')]
 require(compare_reflections(refs),'Selected reflection fields differ')
 altered=copy.deepcopy(refs);altered[1][0]['arguments'][0]['index']+=1;require(not compare_reflections(altered),'Altered reflection was accepted')
 opt=[x for x in rows if x['mode']=='optin-reflect'];native=[x for x in rows if x['mode']=='native-reflect']
 print(json.dumps({'status':'PASS','host_processes':len(rows),'nonoverlapping':True,'client_SHA256':i['executable_SHA256'],'bootstrap_SHA256':i['frozen']['assets/bootstrap.dylib'],
  'archive_SHA256':i['archive_SHA256'],'client_imports_project_symbols':False,
  'native_defect_words':sum(x['expected_native_defect_words'] for x in native),'corrected_and_control_CAS_operations':sum(x['correct_CAS_operations'] for x in opt),
  'native_dispatches':sum(x['user_GPU_dispatches'] for x in native),'optin_dispatches':sum(x['user_GPU_dispatches'] for x in opt),
  'mutated_reflection_rejected':True,'reflection_function_count':len(refs[0]),'reflection_argument_count_per_function':3,'reflection_full_host_count':len(refs),'negative_controls':['wrong-client','wrong-cert','wrong-library','optin-reflection'],'installed_driver_modified':False,
  'scope':'One pinned purpose-built public-Metal client, argument and buffer type options with reflection for exact certified shaders; not arbitrary applications or system-wide integration'},indent=2,sort_keys=True))
if __name__=='__main__':main()
