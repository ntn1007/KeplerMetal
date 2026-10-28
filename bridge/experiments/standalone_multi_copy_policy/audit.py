#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit a bounded cohort of signed, sequential GPU-copy processes."""
import argparse, hashlib, json, subprocess, sys
from collections import Counter
from datetime import datetime
from pathlib import Path
HERE=Path(__file__).resolve().parent
BRIDGE=HERE.parents[1]
def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(condition, reason):
 if not condition: raise ValueError(reason)
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for arg in ('build','source-build','out'): p.add_argument('--'+arg,type=Path,required=True)
 p.add_argument('--hosts',type=Path,nargs='+',required=True)
 a=p.parse_args();build=a.build.resolve();dirs=[x.resolve() for x in a.hosts]
 need(len(dirs)==13 and len(set(dirs))==13 and not a.out.exists() and a.out.parent.is_dir(),'Require 13 distinct processes and a fresh output')
 frozen=read(build/'inputs.json');tested=read(build/'archive-manifest.json');fresh=read(a.source_build/'manifest.json')
 need(fresh['status']=='PASS' and len(tested['object_SHA256'])==7 and tested['object_SHA256']==fresh['object_SHA256'] and tested['source_SHA256']==fresh['source_SHA256'],'Runtime rebuild differs')
 for name,digest in fresh['source_SHA256'].items(): need(sha(BRIDGE/'src'/name)==sha(a.source_build/'src'/name)==digest,'Source differs: '+name)
 for archive in (build/'runtime_archive.a',a.source_build/'libKeplerMetal.a'):
  for name,digest in tested['object_SHA256'].items():need(hashlib.sha256(subprocess.run(['xcrun','ar','-p',str(archive),name],check=True,capture_output=True).stdout).hexdigest()==digest,'Object differs: '+name)
 rows=[];intervals=[];pids=set()
 for d in dirs:
  i=read(d/'inputs.json');m=read(d/'execution/manifest.json');need(i['frozen']==frozen['frozen'] and i['build_inputs_SHA256']==sha(build/'inputs.json') and i['executable_A_SHA256']==frozen['executable_A_SHA256'] and i['executable_B_SHA256']==frozen['executable_B_SHA256'],'Build identity differs');need(i['static_library_SHA256']==frozen['static_library_SHA256'] and sha(d/'runtime_archive.a')==i['static_library_SHA256'],'Archive differs')
  for name in ('client_a.mm','client_b.mm','bootstrap.mm','verify.py','experiment.py'):need(sha(HERE/name)==i['frozen']['src/'+name],'Frozen source differs: '+name)
  need(i['frozen']['src/verify_partial_gpu_dual_copy.py']==sha(BRIDGE/'tools/verify_partial_gpu_dual_copy.py'),'Oracle source differs')
  for name,digest in fresh['source_SHA256'].items():need(i['frozen']['library-src/'+name]==digest,'Runtime source differs: '+name)
  for f in (d/'execution/application',d/'assets/bootstrap.dylib'):subprocess.run(['codesign','--verify','--strict',str(f)],check=True,capture_output=True)
  v=subprocess.run([sys.executable,'-I',str(d/'src/verify.py'),str(d)],capture_output=True,text=True,timeout=120);need(v.returncode==0,'Oracle failed: '+str(d)+' '+v.stderr[-1000:]);r=json.loads(v.stdout);need(r==read(d/'verification.stdout') and r['status']=='PASS','Recorded oracle differs')
  need(m['pid'] not in pids,'Duplicate process');pids.add(m['pid']);intervals.append((datetime.fromisoformat(m['started_at']),datetime.fromisoformat(m['completed_at'])));rows.append(r)
 intervals.sort();need(all(x<=y for x,y in intervals) and all(x[1]<=y[0] for x,y in zip(intervals,intervals[1:])),'Intervals overlap')
 need(Counter(x['mode'] for x in rows)==Counter({'optin-a':8,'optin-b':2,'native-a':1,'wrong-policy':1,'wrong-library':1}),'Mode coverage differs')
 need(Counter((x['scenario'],x['route']) for x in rows if x['mode']=='optin-a')==Counter({(n,r):2 for n in (0,3) for r in ('same','separate')}),'Geometry/route coverage differs')
 need(Counter((x['scenario'],x['route']) for x in rows if x['mode']=='optin-b')==Counter({(0,'same'):1,(3,'separate'):1}),'Regression coverage differs')
 result={'status':'PASS','host_processes':len(rows),'nonoverlapping':True,'positive_A_two_copy_processes':8,'positive_B_one_copy_processes':2,'positive_dispatches':sum(x['GPU_dispatches'] for x in rows),'positive_invocations':sum(x['GPU_invocations'] for x in rows),'correct_uint32_words':sum(x['correct_uint32_words'] for x in rows),'committed_copy_blits':sum(x['committed_copy_blits'] for x in rows),'bootstrap_SHA256':frozen['frozen']['assets/bootstrap.dylib'],'client_A_SHA256':frozen['executable_A_SHA256'],'client_B_SHA256':frozen['executable_B_SHA256'],'runtime_archive_SHA256':frozen['static_library_SHA256'],'independent_runtime_object_members_match':True,'scope':'Two disjoint ICB pairs, pinned shaders and one queue in purpose-built public clients; process-local injection, not general ICB or system driver support.'}
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
