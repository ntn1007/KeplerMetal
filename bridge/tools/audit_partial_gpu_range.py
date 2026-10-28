#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck frozen GPU range cohorts and same-runtime regression evidence."""
import argparse, hashlib, json, subprocess, sys
from collections import Counter
from datetime import datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def read(p): return json.loads(Path(p).read_text())
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok, why):
 if not ok: raise ValueError(why)
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('range','mixed','mixed_uniform','single','snapshot','barrier','uniform'): p.add_argument('--'+name.replace('_','-'),dest=name,type=Path,nargs='+',required=True)
 p.add_argument('--current-source-build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 need(not a.out.exists() and a.out.parent.is_dir(),'Fresh audit output required')
 groups=[('range',a.range,'verify_partial_gpu_range.py'),('mixed',a.mixed,'verify_partial_gpu_mixed.py'),('mixed_uniform',a.mixed_uniform,'verify_partial_gpu_uniform.py'),('single',a.single,'verify_partial_gpu_copy.py'),('snapshot',a.snapshot,'verify_partial_snapshot.py'),('barrier',a.barrier,'verify_partial_chain_barrier.py'),('uniform',a.uniform,'verify_uniform_icb_3d.py')]
 paths=[v for _,ds,_ in groups for v in ds];need(len(paths)==len({x.resolve() for x in paths})==46,'46 distinct hosts required')
 rows=[];intervals=[];pids=set();archives=set()
 for group,dirs,script in groups:
  for raw in dirs:
   d=raw.resolve();i=read(d/'inputs.json');m=read(d/'execution/manifest.json');archives.add(i['runtime_archive_SHA256'])
   for name in ('KeplerCPUICB.mm','KeplerCPUICB.h','KeplerPartialGridPlan.h'):need(i['frozen']['src/'+name]==sha(ROOT/'src'/name),'Runtime source differs: '+name)
   need(i['frozen']['src/'+script]==sha(ROOT/'tools'/script),'Verifier differs: '+script)
   prefix={'range':'partial_gpu_range','mixed':'partial_gpu_mixed','mixed_uniform':'partial_gpu_uniform','single':'partial_gpu_copy'}.get(group)
   if prefix:
    for name in (prefix+'.py',prefix+'_probe.mm'): need(i['frozen']['src/'+name]==sha(ROOT/'tools'/name),'Probe source differs: '+name)
   subprocess.run(['codesign','--verify','--strict',str(d/'execution/application')],check=True,capture_output=True)
   v=subprocess.run([sys.executable,'-I',str(d/'src'/script),str(d)],capture_output=True,text=True,timeout=120);need(v.returncode==0,'Oracle failed: '+str(d)+' '+v.stderr[-1000:]);result=json.loads(v.stdout);need(result==json.loads((d/'verification.stdout').read_text()) and result.get('status',result.get('verification'))=='PASS','Recorded oracle differs');rows.append((group,i,result,d))
   need(m['pid'] not in pids,'Duplicate PID');pids.add(m['pid']);intervals.append((datetime.fromisoformat(m['started_at']),datetime.fromisoformat(m['completed_at'])))
 need(len(archives)==1,'Runtime archive differs');tested=read(rows[0][3]/'archive-manifest.json');fresh=read(a.current_source_build/'manifest.json');need(fresh['status']=='PASS' and len(tested['object_SHA256'])==7 and tested['object_SHA256']==fresh['object_SHA256'] and tested['source_SHA256']==fresh['source_SHA256'],'Independent rebuild differs')
 for name,digest in fresh['source_SHA256'].items():need(sha(ROOT/'src'/name)==digest and sha(a.current_source_build/'src'/name)==digest,'Fresh source differs: '+name)
 for archive in (rows[0][3]/'runtime_archive.a',a.current_source_build/'libKeplerMetal.a'):
  for name,digest in tested['object_SHA256'].items():need(hashlib.sha256(subprocess.run(['xcrun','ar','-p',str(archive),name],check=True,capture_output=True).stdout).hexdigest()==digest,'Archive member differs: '+name)
 want=Counter({(s,m):(2 if m in ('same','separate') else 1) for s in (0,3) for m in ('prepare','native','same','separate')})
 summary={}
 for group in ('range','mixed','mixed_uniform'):
  cases=[r[2] for r in rows if r[0]==group];need(Counter((x['scenario'],x['mode']) for x in cases)==want,'Coverage differs: '+group)
  copied=[x for x in cases if x['mode'] in ('same','separate')];base=[x for x in cases if x['mode']=='native'];prep=[x for x in cases if x['mode']=='prepare']
  summary[group]={'hosts':len(cases),'copied_user_dispatches':sum(x['GPU_user_dispatches'] for x in copied),'copied_invocations':sum(x['GPU_invocations'] for x in copied),'correct_uint32_words':sum(x['correct_uint32_words'] for x in copied),'committed_blits':sum(x['copy_blits'] for x in copied),'uncommitted_prepare_blits':sum(x['copy_blits'] for x in prep),'baseline_invocations':sum(x['GPU_invocations'] for x in base),'predecessor_refusals':sum(x['uncommitted_order_refused'] for x in copied)}
 single=[r[2] for r in rows if r[0]=='single'];snap=[r[2] for r in rows if r[0]=='snapshot'];barrier=[r[2] for r in rows if r[0]=='barrier'];uniform=[r[2] for r in rows if r[0]=='uniform']
 need(Counter((x['scenario'],x['mode']) for x in single)==Counter((s,m) for s in (0,3) for m in ('same','separate')),'Single-copy coverage differs')
 need({x['scenario'] for x in snap}=={'partial_partial','partial_partial_3d_limit'} and {x['case'] for x in barrier}=={0,6} and {x['form'] for x in uniform}=={'groups','threads'},'Regression coverage differs')
 intervals.sort();need(all(x<=y for x,y in intervals) and all(x[1]<=y[0] for x,y in zip(intervals,intervals[1:])),'Host intervals overlap')
 result={'status':'PASS','host_processes':len(rows),'nonoverlapping':True,'runtime_archive_SHA256':next(iter(archives)),'fresh_archive_SHA256':fresh['static_library_SHA256'],'fresh_object_members_match':True,'cohorts':summary,'single_regression_invocations':sum(x['GPU_invocations'] for x in single),'snapshot_regression_invocations':sum(x['invocations'] for x in snap),'barrier_regression_invocations':sum(x['threads'] for x in barrier),'uniform_regression_invocations':sum(x['GPU_invocations_counted'] for x in uniform),'source_SHA256':{n:sha(ROOT/'src'/n) for n in ('KeplerCPUICB.mm','KeplerCPUICB.h','KeplerPartialGridPlan.h')},'scope':'Opted-in preflighted prepared partial project ICB ranges up to eight regions; mixed serial execution of copied and existing partial or uniform slots; not native Apple ICB.'}
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
