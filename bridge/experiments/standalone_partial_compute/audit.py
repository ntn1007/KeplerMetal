#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck public-client ICB runs, source identities and a separate runtime build."""
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
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--hosts',type=Path,nargs='+',required=True);p.add_argument('--render',type=Path,required=True);p.add_argument('--copy',type=Path,nargs='+',required=True);p.add_argument('--current-source-build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 need(len(a.hosts)==len({x.resolve() for x in a.hosts})==9 and not a.out.exists() and a.out.parent.is_dir(),'Nine distinct hosts and fresh output required')
 rows=[];pids=set();intervals=[];archives=set()
 for raw in a.hosts:
  d=raw.resolve();i=read(d/'inputs.json');h=read(d/'execution/manifest.json');archives.add(i['static_library_SHA256']);need(sha(d/'runtime_archive.a')==i['static_library_SHA256'],'Archive differs')
  for name in ('client.mm','bootstrap.mm','verify.py','experiment.py'):need(i['frozen']['src/'+name]==sha(HERE/name),'Source differs: '+name)
  need(i['frozen']['src/verify_partial_gpu_dual_copy.py']==sha(BRIDGE/'tools/verify_partial_gpu_dual_copy.py'),'CPU oracle differs')
  for name in read(d/'archive-manifest.json')['source_SHA256']:need(i['frozen']['library-src/'+name]==sha(BRIDGE/'src'/name),'Runtime source differs: '+name)
  subprocess.run(['codesign','--verify','--strict',str(d/'execution/application')],check=True,capture_output=True);subprocess.run(['codesign','--verify','--strict',str(d/'assets/bootstrap.dylib')],check=True,capture_output=True)
  v=subprocess.run([sys.executable,'-I',str(d/'src/verify.py'),str(d)],capture_output=True,text=True,timeout=120);need(v.returncode==0,'Oracle failed: '+str(d)+' '+v.stderr[-1000:]);r=json.loads(v.stdout);need(r==json.loads((d/'verification.stdout').read_text()) and r['status']=='PASS','Oracle differs');rows.append((i,r,d))
  need(h['pid'] not in pids,'Duplicate PID');pids.add(h['pid']);intervals.append((datetime.fromisoformat(h['started_at']),datetime.fromisoformat(h['completed_at'])))
  if i['mode']=='wrong-client':need(i['run_executable_SHA256']!=i['executable_SHA256'],'Wrong client is unchanged')
  if i['mode']=='wrong-manifest':need(sha(d/'assets/wrong.json')!=sha(d/'assets/partial_dual.json'),'Wrong manifest is unchanged')
  if i['mode']=='wrong-library':need(sha(d/'assets/wrong.metallib')!=sha(d/'assets/partial_dual.metallib'),'Wrong library is unchanged')
 need(len(archives)==1,'Runtime archive differs');test=read(rows[0][2]/'archive-manifest.json');fresh=read(a.current_source_build/'manifest.json');need(fresh['status']=='PASS' and len(test['object_SHA256'])==7 and test['object_SHA256']==fresh['object_SHA256'] and test['source_SHA256']==fresh['source_SHA256'],'Independent rebuild differs')
 for name,digest in fresh['source_SHA256'].items():need(sha(BRIDGE/'src'/name)==digest and sha(a.current_source_build/'src'/name)==digest,'Rebuilt source differs: '+name)
 for archive in (rows[0][2]/'runtime_archive.a',a.current_source_build/'libKeplerMetal.a'):
  for name,digest in test['object_SHA256'].items():need(hashlib.sha256(subprocess.run(['xcrun','ar','-p',str(archive),name],check=True,capture_output=True).stdout).hexdigest()==digest,'Archive member differs: '+name)
 symbols=subprocess.run(['nm','-u',str(rows[0][2]/'application')],check=True,capture_output=True,text=True).stdout;need('Kepler' not in symbols and 'KPCPU' not in symbols,'Public client imports project symbols')
 want=Counter({('auto',0):2,('auto',3):2,('native',0):1,('native',3):1,('wrong-client',0):1,('wrong-manifest',0):1,('wrong-library',0):1});need(Counter((r['mode'],r['scenario']) for _,r,_ in rows)==want,'Cohort differs')
 need(len(a.copy)==2 and len({a.render.resolve(),*(x.resolve() for x in a.copy),*(x.resolve() for x in a.hosts)})==12,'Twelve distinct hosts required')
 regressions=[]
 for group,dirs,script in [('render',[a.render],'verify.py'),('copy',a.copy,'verify_partial_gpu_mixed_copy.py')]:
  for raw in dirs:
   d=raw.resolve();i=read(d/'inputs.json');h=read(d/'execution/manifest.json');archive=i['static_library_SHA256'] if group=='render' else i['runtime_archive_SHA256'];need(archive==next(iter(archives)),'Regression runtime differs')
   if group=='copy':
    need(sha(d/'runtime_archive.a')==archive,'Regression archive differs')
    for name in ('KeplerCPUICB.mm','KeplerCPUICB.h','KeplerPartialGridPlan.h'):need(i['frozen']['src/'+name]==sha(BRIDGE/'src'/name),'Regression source differs: '+name)
    for name in ('partial_gpu_mixed_copy.py','partial_gpu_mixed_copy_probe.mm',script):need(i['frozen']['src/'+name]==sha(BRIDGE/'tools'/name),'Regression tool differs: '+name)
   else:
    for name,digest in test['source_SHA256'].items():need(i['frozen']['library-src/'+name]==digest,'Render source differs: '+name)
    for name in ('client.mm','bootstrap.mm',script):need(i['frozen']['src/'+name]==sha(BRIDGE/'experiments/standalone_icb'/name),'Render source differs: '+name)
    subprocess.run(['codesign','--verify','--strict',str(d/'assets/bootstrap.dylib')],check=True,capture_output=True)
   subprocess.run(['codesign','--verify','--strict',str(d/'execution/application')],check=True,capture_output=True)
   v=subprocess.run([sys.executable,'-I',str(d/'src'/script),str(d)],capture_output=True,text=True,timeout=120);need(v.returncode==0,'Regression oracle failed: '+str(d)+' '+v.stderr[-1000:]);r=json.loads(v.stdout);need(r==json.loads((d/'verification.stdout').read_text()) and r['status']=='PASS','Regression result differs');regressions.append((group,r))
   need(h['pid'] not in pids,'Duplicate PID');pids.add(h['pid']);intervals.append((datetime.fromisoformat(h['started_at']),datetime.fromisoformat(h['completed_at'])))
 need(Counter((r['mode'],r['scenario']) for group,r in regressions if group=='copy')==Counter((('same',0),('same',3))) and [r['mode'] for group,r in regressions if group=='render']==['auto'],'Regression coverage differs')
 intervals.sort();need(all(x<=y for x,y in intervals) and all(x[1]<=y[0] for x,y in zip(intervals,intervals[1:])),'Hosts overlap')
 result={'status':'PASS','host_processes':len(rows)+len(regressions),'standalone_compute_hosts':len(rows),'regression_hosts':len(regressions),'render_regression_checked_float_channels':sum(r.get('gpu_pixels_checked',0) for group,r in regressions if group=='render'),'copy_regression_invocations':sum(r['GPU_invocations'] for group,r in regressions if group=='copy'),'nonoverlapping':True,'runtime_archive_SHA256':next(iter(archives)),'fresh_archive_SHA256':fresh['static_library_SHA256'],'fresh_object_members_match':True,'public_client_imports_project_symbols':False,'positive_dispatches':sum(r['GPU_dispatches'] for _,r,_ in rows),'positive_invocations':sum(r['GPU_invocations'] for _,r,_ in rows),'correct_uint32_words':sum(r['correct_uint32_words'] for _,r,_ in rows),'native_missing_ICB_controls':2,'identity_or_library_refusals':3,'client_SHA256':sha(HERE/'client.mm'),'bootstrap_SHA256':sha(HERE/'bootstrap.mm'),'scope':'One explicitly launched pinned public-Metal test client, one pinned dual-function library, one qualified GTX and one queue; no general transparent driver support.'}
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
