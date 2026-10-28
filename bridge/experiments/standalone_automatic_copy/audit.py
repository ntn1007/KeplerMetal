#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck isolated public-Metal GPU ICB copies and same-runtime controls."""
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
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--hosts',type=Path,nargs='+',required=True);p.add_argument('--labelled',type=Path,nargs='+',required=True);p.add_argument('--compute',type=Path,nargs='+',required=True);p.add_argument('--render',type=Path,required=True);p.add_argument('--copy',type=Path,nargs='+',required=True);p.add_argument('--current-source-build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 paths=a.hosts+a.labelled+a.compute+[a.render]+a.copy;need(len(paths)==len({x.resolve() for x in paths})==20 and len(a.hosts)==13 and len(a.labelled)==2 and len(a.compute)==2 and len(a.copy)==2 and not a.out.exists() and a.out.parent.is_dir(),'20 distinct hosts and fresh output required')
 rows=[];pids=set();intervals=[];archives=set()
 groups=[('copy-client',a.hosts,HERE,'verify.py'),('labelled',a.labelled,BRIDGE/'experiments/standalone_partial_copy','verify.py'),('compute',a.compute,BRIDGE/'experiments/standalone_partial_compute','verify.py'),('render',[a.render],BRIDGE/'experiments/standalone_icb','verify.py'),('copy',a.copy,BRIDGE/'tools','verify_partial_gpu_mixed_copy.py')]
 for group,dirs,source,script in groups:
  for raw in dirs:
   d=raw.resolve();i=read(d/'inputs.json');h=read(d/'execution/manifest.json');archive=i['runtime_archive_SHA256'] if group=='copy' else i['static_library_SHA256'];archives.add(archive)
   if group!='render':need(sha(d/'runtime_archive.a')==archive,'Runtime archive differs')
   if group in ('copy-client','labelled','compute','render'):
    for name in ('client.mm','bootstrap.mm',script):need(i['frozen']['src/'+name]==sha(source/name),'Client source differs: '+name)
    if group!='render':need(i['frozen']['src/experiment.py']==sha(source/'experiment.py') and i['frozen']['src/verify_partial_gpu_dual_copy.py']==sha(BRIDGE/'tools/verify_partial_gpu_dual_copy.py'),'Experiment or CPU oracle differs')
    for name,digest in read(a.current_source_build/'manifest.json')['source_SHA256'].items():need(i['frozen']['library-src/'+name]==digest==sha(BRIDGE/'src'/name),'Runtime source differs: '+name)
    subprocess.run(['codesign','--verify','--strict',str(d/'assets/bootstrap.dylib')],check=True,capture_output=True)
   else:
    for name in ('KeplerCPUICB.mm','KeplerCPUICB.h','KeplerPartialGridPlan.h'):need(i['frozen']['src/'+name]==sha(BRIDGE/'src'/name),'Runtime source differs: '+name)
    for name in ('partial_gpu_mixed_copy.py','partial_gpu_mixed_copy_probe.mm',script):need(i['frozen']['src/'+name]==sha(source/name),'Copy source differs: '+name)
   subprocess.run(['codesign','--verify','--strict',str(d/'execution/application')],check=True,capture_output=True)
   v=subprocess.run([sys.executable,'-I',str(d/'src'/script),str(d)],capture_output=True,text=True,timeout=120);need(v.returncode==0,'Oracle failed: '+str(d)+' '+v.stderr[-1000:]);r=json.loads(v.stdout);need(r==read(d/'verification.stdout') and r['status']=='PASS','Recorded oracle differs');rows.append((group,i,r,d))
   need(h['pid'] not in pids,'Duplicate PID');pids.add(h['pid']);intervals.append((datetime.fromisoformat(h['started_at']),datetime.fromisoformat(h['completed_at'])))
   if group=='copy-client':
    if i['mode']=='wrong-client':need(i['run_executable_SHA256']!=i['executable_SHA256'],'Wrong client unchanged')
    if i['mode']=='wrong-manifest':need(sha(d/'assets/wrong.json')!=sha(d/'assets/partial_dual.json'),'Wrong manifest unchanged')
    if i['mode']=='wrong-library':need(sha(d/'assets/wrong.metallib')!=sha(d/'assets/partial_dual.metallib'),'Wrong library unchanged')
 need(len(archives)==1,'Runtime archive differs');tested=read(rows[0][3]/'archive-manifest.json');fresh=read(a.current_source_build/'manifest.json');need(fresh['status']=='PASS' and len(tested['object_SHA256'])==7 and tested['object_SHA256']==fresh['object_SHA256'] and tested['source_SHA256']==fresh['source_SHA256'],'Independent rebuild differs')
 for name,digest in fresh['source_SHA256'].items():need(sha(BRIDGE/'src'/name)==digest and sha(a.current_source_build/'src'/name)==digest,'Rebuilt source differs: '+name)
 for archive in (rows[0][3]/'runtime_archive.a',a.current_source_build/'libKeplerMetal.a'):
  for name,digest in tested['object_SHA256'].items():need(hashlib.sha256(subprocess.run(['xcrun','ar','-p',str(archive),name],check=True,capture_output=True).stdout).hexdigest()==digest,'Archive member differs: '+name)
 symbols=subprocess.run(['nm','-u',str(rows[0][3]/'application')],check=True,capture_output=True,text=True).stdout;need('Kepler' not in symbols and 'KPCPU' not in symbols,'Public client imports project symbols')
 cohort=[r for group,_,r,_ in rows if group=='copy-client'];want=Counter({**{('auto',s,t):2 for s in (0,3) for t in ('same','separate')},('native',0,'same'):1,('native',3,'same'):1,('wrong-client',0,'same'):1,('wrong-manifest',0,'same'):1,('wrong-library',0,'same'):1});need(Counter((r['mode'],r['scenario'],r['route']) for r in cohort)==want,'Cohort differs')
 need(Counter((r['mode'],r['scenario'],r['route']) for group,_,r,_ in rows if group=='labelled')==Counter((('auto',0,'same'),('auto',3,'separate'))) and Counter((r['mode'],r['scenario']) for group,_,r,_ in rows if group=='compute')==Counter((('auto',0),('auto',3))) and Counter((r['mode'],r['scenario']) for group,_,r,_ in rows if group=='copy')==Counter((('same',0),('same',3))) and [r['mode'] for group,_,r,_ in rows if group=='render']==['auto'],'Prior control coverage differs')
 intervals.sort();need(all(x<=y for x,y in intervals) and all(x[1]<=y[0] for x,y in zip(intervals,intervals[1:])),'Hosts overlap')
 result={'status':'PASS','host_processes':len(rows),'new_copy_client_hosts':len(cohort),'new_same_runtime_control_hosts':7,'nonoverlapping':True,'runtime_archive_SHA256':next(iter(archives)),'fresh_archive_SHA256':fresh['static_library_SHA256'],'fresh_object_members_match':True,'public_client_imports_project_symbols':False,'positive_dispatches':sum(r['GPU_dispatches'] for r in cohort),'positive_invocations':sum(r['GPU_invocations'] for r in cohort),'correct_uint32_words':sum(r['correct_uint32_words'] for r in cohort),'committed_copy_blits':sum(r['committed_copy_blits'] for r in cohort),'native_missing_ICB_controls':2,'identity_or_library_refusals':3,'same_queue_separate_order_runs':sum(r['mode']=='auto' and r['route']=='separate' for r in cohort),'no_label_dependency':('copyLabel' not in (HERE/'bootstrap.mm').read_text() and '.label=' not in (HERE/'client.mm').read_text()),'client_SHA256':sha(HERE/'client.mm'),'bootstrap_SHA256':sha(HERE/'bootstrap.mm'),'scope':'One explicitly launched pinned public-Metal test client, object-based, unlabelled copy interception, one pinned dual-function registration and one queue; not general transparent driver support.'}
 need(result['no_label_dependency'],'Label dependency present')
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
