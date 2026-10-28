#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck policy, two public clients and GPU-copy evidence."""
from pathlib import Path
from collections import Counter
from datetime import datetime
import argparse,hashlib,json,subprocess,sys
HERE=Path(__file__).resolve().parent;BRIDGE=HERE.parents[1]
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(v,msg):
 if not v:raise ValueError(msg)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--hosts',type=Path,nargs='+',required=True);p.add_argument('--same-policy-a',type=Path,nargs='+',required=True);p.add_argument('--previous',type=Path,nargs='+',required=True);p.add_argument('--current-source-build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();build=a.build.resolve();paths=a.hosts+a.same_policy_a+a.previous
 need(len(paths)==len({x.resolve() for x in paths})==22 and len(a.hosts)==16 and len(a.same_policy_a)==2 and len(a.previous)==4 and not a.out.exists() and a.out.parent.is_dir(),'22 distinct hosts and fresh output required')
 b=read(build/'inputs.json');A=b['executable_A_SHA256'];B=b['executable_B_SHA256'];need(A!=B and sha(build/'application')==A and sha(build/'application-b')==B,'Client identities differ');need(read(build/'assets/policy-a.json')=={'version':1,'allowed_clients':[A]} and read(build/'assets/policy-ab.json')=={'version':1,'allowed_clients':[A,B]} and read(build/'assets/policy-duplicate.json')=={'version':1,'allowed_clients':[A,A]},'Policy contents differ')
 need(sha(HERE/'client_a.mm')==sha(BRIDGE/'experiments/standalone_automatic_copy/client.mm') and sha(HERE/'client_b.mm')==sha(BRIDGE/'experiments/standalone_partial_copy/client.mm'),'Related-client source provenance differs')
 fresh=read(a.current_source_build/'manifest.json');tested=read(build/'archive-manifest.json');need(fresh['status']=='PASS' and len(tested['object_SHA256'])==7 and tested['object_SHA256']==fresh['object_SHA256'] and tested['source_SHA256']==fresh['source_SHA256'],'Independent runtime rebuild differs')
 for name,digest in fresh['source_SHA256'].items():need(sha(BRIDGE/'src'/name)==digest and sha(a.current_source_build/'src'/name)==digest,'Runtime source differs: '+name)
 for archive in (build/'runtime_archive.a',a.current_source_build/'libKeplerMetal.a'):
  for name,digest in tested['object_SHA256'].items():need(hashlib.sha256(subprocess.run(['xcrun','ar','-p',str(archive),name],check=True,capture_output=True).stdout).hexdigest()==digest,'Archive member differs: '+name)
 rows=[];intervals=[];pids=set();boots=set();archives=set()
 for group,dirs,source in [('policy',a.hosts,HERE),('same-policy',a.same_policy_a,HERE),('previous',a.previous,BRIDGE/'experiments/standalone_automatic_copy')]:
  for raw in dirs:
   d=raw.resolve();i=read(d/'inputs.json');h=read(d/'execution/manifest.json');archives.add(i['static_library_SHA256']);boots.add(i['frozen']['assets/bootstrap.dylib'] if group!='previous' else None)
   need(sha(d/'runtime_archive.a')==i['static_library_SHA256'],'Runtime archive differs')
   names=('client_a.mm','client_b.mm','bootstrap.mm','verify.py','experiment.py') if group!='previous' else ('client.mm','bootstrap.mm','verify.py','experiment.py')
   for name in names:need(i['frozen']['src/'+name]==sha(source/name),'Frozen source differs: '+name)
   need(i['frozen']['src/verify_partial_gpu_dual_copy.py']==sha(BRIDGE/'tools/verify_partial_gpu_dual_copy.py'),'CPU oracle differs')
   for name,digest in fresh['source_SHA256'].items():need(i['frozen']['library-src/'+name]==digest,'Host runtime source differs: '+name)
   for f in (d/'execution/application',d/'assets/bootstrap.dylib'):subprocess.run(['codesign','--verify','--strict',str(f)],check=True,capture_output=True)
   v=subprocess.run([sys.executable,'-I',str(d/'src/verify.py'),str(d)],capture_output=True,text=True,timeout=120);need(v.returncode==0,'Oracle failed: '+str(d)+' '+v.stderr[-1000:]);r=json.loads(v.stdout);need(r==read(d/'verification.stdout') and r['status']=='PASS','Recorded result differs');rows.append((group,i,r))
   if group=='same-policy':need(i['policy_name']=='policy-ab.json' and i['policy_expected_SHA256']==sha(build/'assets/policy-ab.json') and i['same_policy_runner_SHA256']==sha(HERE/'same_policy.py'),'Shared policy runner differs')
   need(h['pid'] not in pids,'Duplicate PID');pids.add(h['pid']);intervals.append((datetime.fromisoformat(h['started_at']),datetime.fromisoformat(h['completed_at'])))
 need(len(archives)==1 and next(iter(archives))==b['static_library_SHA256'] and boots=={None,b['frozen']['assets/bootstrap.dylib']},'Bootstrap or runtime differs')
 for app in (build/'application',build/'application-b'):
  symbols=subprocess.run(['nm','-u',str(app)],check=True,capture_output=True,text=True).stdout;need('Kepler' not in symbols and 'KPCPU' not in symbols,'Client imports project symbols')
 cohort=[r for group,_,r in rows if group in ('policy','same-policy')];want=Counter({'optin-a':6,'optin-b':4,'native-a':1,'native-b':1,'denied-b':1,'wrong-policy':1,'malformed-policy':1,'wrong-client':1,'wrong-manifest':1,'wrong-library':1});need(Counter(r['mode'] for r in cohort)==want,'Mode coverage differs')
 for mode in ('optin-a','optin-b'):need(Counter((r['scenario'],r['route']) for r in cohort if r['mode']==mode)==Counter({(0,'same'):(3 if mode=='optin-a' else 2),(3,'separate'):(3 if mode=='optin-a' else 2)}),'Opt-in coverage differs: '+mode)
 prior=[r for group,_,r in rows if group=='previous'];need(Counter((r['scenario'],r['route']) for r in prior)==Counter({(0,'same'):2,(3,'separate'):2}) and all(r['mode']=='auto' for r in prior),'Previous coverage differs')
 intervals.sort();need(all(x<=y for x,y in intervals) and all(x[1]<=y[0] for x,y in zip(intervals,intervals[1:])),'Hosts overlap')
 result={'status':'PASS','host_processes':len(rows),'new_policy_hosts':len(cohort),'reused_previous_control_hosts':len(prior),'nonoverlapping':True,'runtime_archive_SHA256':b['static_library_SHA256'],'fresh_archive_SHA256':fresh['static_library_SHA256'],'fresh_object_members_match':True,'bootstrap_SHA256':b['frozen']['assets/bootstrap.dylib'],'client_A_SHA256':A,'client_B_SHA256':B,'policy_A_SHA256':sha(build/'assets/policy-a.json'),'policy_AB_SHA256':sha(build/'assets/policy-ab.json'),'public_client_imports_project_symbols':False,'positive_dispatches':sum(r['GPU_dispatches'] for r in cohort),'positive_invocations':sum(r['GPU_invocations'] for r in cohort),'correct_uint32_words':sum(r['correct_uint32_words'] for r in cohort),'committed_copy_blits':sum(r['committed_copy_blits'] for r in cohort),'native_missing_ICB_controls':2,'policy_or_identity_refusals':6,'both_clients_exercised_with_AB_policy':True,'scope':'Two related purpose-built public-Metal clients, same process-local bootstrap and exact dual-function registration; caller-controlled policy is not a security authority or proof of third-party compatibility.'}
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
