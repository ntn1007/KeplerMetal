#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit partial GPU-copy hosts and same-runtime regressions."""
import argparse, hashlib, json, subprocess, sys
from collections import Counter
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(v,why):
 if not v:raise ValueError(why)
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for name in ('copy','snapshot','barrier','uniform'):p.add_argument('--'+name,type=Path,nargs='+',required=True)
 p.add_argument('--current-source-build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'Fresh audit output required')
 paths=a.copy+a.snapshot+a.barrier+a.uniform;need(len(paths)==len({x.resolve() for x in paths})==18,'Eighteen distinct hosts required');rows=[];intervals=[];pids=set();archives=set()
 for group,dirs,script in [('copy',a.copy,'verify_partial_gpu_copy.py'),('snapshot',a.snapshot,'verify_partial_snapshot.py'),('barrier',a.barrier,'verify_partial_chain_barrier.py'),('uniform',a.uniform,'verify_uniform_icb_3d.py')]:
  for raw in dirs:
   d=raw.resolve();i=read(d/'inputs.json');m=read(d/'execution/manifest.json');archives.add(i['runtime_archive_SHA256'])
   for name in ('KeplerCPUICB.mm','KeplerCPUICB.h','KeplerPartialGridPlan.h'):need(i['frozen']['src/'+name]==sha(ROOT/'src'/name),'Runtime source differs: '+name)
   need(i['frozen']['src/'+script]==sha(ROOT/'tools'/script),'Verifier differs: '+script)
   if group=='copy':
    for name in ('partial_gpu_copy.py','partial_gpu_copy_probe.mm'):need(i['frozen']['src/'+name]==sha(ROOT/'tools'/name),'Copy source differs: '+name)
   subprocess.run(['codesign','--verify','--strict',str(d/'execution/application')],check=True,capture_output=True)
   v=subprocess.run([sys.executable,'-I',str(d/'src'/script),str(d)],capture_output=True,text=True,timeout=120);need(v.returncode==0,'Oracle failed: '+str(d)+' '+v.stderr[-1000:]);result=json.loads(v.stdout);need(result==json.loads((d/'verification.stdout').read_text()) and result.get('status',result.get('verification'))=='PASS','Recorded oracle differs');rows.append((group,i,result,d))
   need(m['pid'] not in pids,'Duplicate PID');pids.add(m['pid']);intervals.append((datetime.fromisoformat(m['started_at']),datetime.fromisoformat(m['completed_at'])))
 need(len(archives)==1,'Runtime archive differs');tested=read(rows[0][3]/'archive-manifest.json');fresh=read(a.current_source_build/'manifest.json');need(fresh['status']=='PASS' and len(tested['object_SHA256'])==7 and tested['object_SHA256']==fresh['object_SHA256'] and tested['source_SHA256']==fresh['source_SHA256'],'Independent rebuild differs')
 for name,digest in fresh['source_SHA256'].items():need(sha(ROOT/'src'/name)==digest and sha(a.current_source_build/'src'/name)==digest,'Fresh source differs: '+name)
 for archive in (rows[0][3]/'runtime_archive.a',a.current_source_build/'libKeplerMetal.a'):
  for name,digest in tested['object_SHA256'].items():need(hashlib.sha256(subprocess.run(['xcrun','ar','-p',str(archive),name],check=True,capture_output=True).stdout).hexdigest()==digest,'Archive member differs: '+name)
 copy=[r[2] for r in rows if r[0]=='copy'];want=Counter({(s,m):(2 if m in ('same','separate') else 1) for s in (0,3) for m in ('prepare','native','same','separate')});need(Counter((x['scenario'],x['mode']) for x in copy)==want,'Copy coverage differs')
 snap=[r[2] for r in rows if r[0]=='snapshot'];barrier=[r[2] for r in rows if r[0]=='barrier'];uniform=[r[2] for r in rows if r[0]=='uniform'];need({x['scenario'] for x in snap}=={'partial_partial','partial_partial_3d_limit'} and {x['case'] for x in barrier}=={0,6} and {x['form'] for x in uniform}=={'groups','threads'},'Regression coverage differs')
 intervals.sort();need(all(x<=y for x,y in intervals) and all(x[1]<=y[0] for x,y in zip(intervals,intervals[1:])),'Host intervals overlap')
 copied=[x for x in copy if x['mode'] in ('same','separate')];baseline=[x for x in copy if x['mode']=='native'];prepared=[x for x in copy if x['mode']=='prepare']
 result={'status':'PASS','host_processes':len(rows),'nonoverlapping':True,'runtime_archive_SHA256':next(iter(archives)),'fresh_archive_SHA256':fresh['static_library_SHA256'],'fresh_object_members_match':True,'copy_hosts':len(copy),'copied_user_dispatches':sum(x['GPU_user_dispatches'] for x in copied),'copied_invocations':sum(x['GPU_invocations'] for x in copied),'copied_correct_uint32_words':sum(x['correct_uint32_words'] for x in copied),'committed_copy_blits':sum(x['copy_blits'] for x in copied),'uncommitted_prepare_blits':sum(x['copy_blits'] for x in prepared),'baseline_invocations':sum(x['GPU_invocations'] for x in baseline),'separate_uncommitted_predecessor_refusals':sum(x['uncommitted_order_refused'] for x in copied),'geometry_and_region_limit_refusals':len(copy),'snapshot_regression_invocations':sum(x['invocations'] for x in snap),'barrier_regression_invocations':sum(x['threads'] for x in barrier),'uniform_regression_invocations':sum(x['GPU_invocations_counted'] for x in uniform),'source_SHA256':{n:sha(ROOT/'src'/n) for n in ('KeplerCPUICB.mm','KeplerCPUICB.h','KeplerPartialGridPlan.h')},'scope':'One explicitly opted-in prepared equal-geometry partial project ICB command, up to eight regions; not native Apple ICB or general GPU command generation.'}
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
