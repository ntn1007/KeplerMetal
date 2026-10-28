#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit dual-pipeline partial/uniform GPU copies and previous-runtime controls."""
import argparse,hashlib,json,subprocess,sys
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
 for name in ('dual','mixed','range','single'):p.add_argument('--'+name,type=Path,nargs='+',required=True)
 p.add_argument('--current-source-build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'Fresh output required')
 groups=[('dual',a.dual,'partial_gpu_dual_copy'),('mixed',a.mixed,'partial_gpu_mixed_copy'),('range',a.range,'partial_gpu_range'),('single',a.single,'partial_gpu_copy')];paths=[d for _,ds,_ in groups for d in ds];need(len(paths)==len({x.resolve() for x in paths})==18,'18 distinct hosts required')
 rows=[];pids=set();intervals=[];archives=set()
 for group,dirs,prefix in groups:
  for raw in dirs:
   d=raw.resolve();i=read(d/'inputs.json');m=read(d/'execution/manifest.json');archives.add(i['runtime_archive_SHA256']);script='verify_'+prefix+'.py'
   for name in ('KeplerCPUICB.mm','KeplerCPUICB.h','KeplerPartialGridPlan.h'):need(i['frozen']['src/'+name]==sha(ROOT/'src'/name),'Runtime source differs: '+name)
   for name in (script,prefix+'.py',prefix+'_probe.mm'):need(i['frozen']['src/'+name]==sha(ROOT/'tools'/name),'Frozen tool differs: '+name)
   subprocess.run(['codesign','--verify','--strict',str(d/'execution/application')],check=True,capture_output=True)
   target=ROOT/'tools/verify_partial_gpu_dual_profiles.py' if group=='dual' else d/'src'/script
   v=subprocess.run([sys.executable,'-I',str(target),str(d)],capture_output=True,text=True,timeout=120);need(v.returncode==0,'Oracle failed: '+str(d)+' '+v.stderr[-1000:]);result=json.loads(v.stdout);base=dict(result)
   if group=='dual':need(base.pop('dual_pipeline_profiles_checked',False),'Dual profiles not checked')
   need(base==json.loads((d/'verification.stdout').read_text()) and base.get('status')=='PASS','Recorded oracle differs');rows.append((group,base,d))
   need(m['pid'] not in pids,'Duplicate PID');pids.add(m['pid']);intervals.append((datetime.fromisoformat(m['started_at']),datetime.fromisoformat(m['completed_at'])))
 need(len(archives)==1,'Runtime differs');tested=read(rows[0][2]/'archive-manifest.json');fresh=read(a.current_source_build/'manifest.json');need(fresh['status']=='PASS' and len(tested['object_SHA256'])==7 and tested['object_SHA256']==fresh['object_SHA256'] and tested['source_SHA256']==fresh['source_SHA256'],'Independent rebuild differs')
 for name,digest in fresh['source_SHA256'].items():need(sha(ROOT/'src'/name)==digest and sha(a.current_source_build/'src'/name)==digest,'Source differs: '+name)
 for archive in (rows[0][2]/'runtime_archive.a',a.current_source_build/'libKeplerMetal.a'):
  for name,digest in tested['object_SHA256'].items():need(hashlib.sha256(subprocess.run(['xcrun','ar','-p',str(archive),name],check=True,capture_output=True).stdout).hexdigest()==digest,'Archive member differs: '+name)
 cohort=[r[1] for r in rows if r[0]=='dual'];want=Counter({(s,m):(2 if m in ('same','separate') else 1) for s in (0,3) for m in ('prepare','native','same','separate')});need(Counter((x['scenario'],x['mode']) for x in cohort)==want,'Dual coverage differs')
 for name in ('mixed','range','single'):
  cases=[r[1] for r in rows if r[0]==name];need(Counter((x['scenario'],x['mode']) for x in cases)==Counter((s,'same') for s in (0,3)),'Prior control coverage differs: '+name)
 intervals.sort();need(all(x<=y for x,y in intervals) and all(x[1]<=y[0] for x,y in zip(intervals,intervals[1:])),'Host intervals overlap')
 copied=[x for x in cohort if x['mode'] in ('same','separate')];base=[x for x in cohort if x['mode']=='native'];prep=[x for x in cohort if x['mode']=='prepare']
 result={'status':'PASS','host_processes':len(rows),'new_dual_hosts':len(cohort),'reused_previous_control_hosts':6,'nonoverlapping':True,'runtime_archive_SHA256':next(iter(archives)),'fresh_archive_SHA256':fresh['static_library_SHA256'],'fresh_object_members_match':True,'copied_user_dispatches':sum(x['GPU_user_dispatches'] for x in copied),'copied_invocations':sum(x['GPU_invocations'] for x in copied),'correct_uint32_words':sum(x['correct_uint32_words'] for x in copied),'committed_copy_blits':sum(x['copy_blits'] for x in copied),'uncommitted_prepare_blits':sum(x['copy_blits'] for x in prep),'baseline_invocations':sum(x['GPU_invocations'] for x in base),'pipeline_mismatch_refusals':sum(x['pipeline_mismatch_refused'] for x in cohort),'uncommitted_predecessor_refusals':sum(x['uncommitted_order_refused'] for x in copied),'reused_controls':{name:sum(r[1]['GPU_invocations'] for r in rows if r[0]==name) for name in ('mixed','range','single')},'profile_verifier_SHA256':sha(ROOT/'tools/verify_partial_gpu_dual_profiles.py'),'source_SHA256':{n:sha(ROOT/'src'/n) for n in ('KeplerCPUICB.mm','KeplerCPUICB.h','KeplerPartialGridPlan.h')},'scope':'Bounded project ICB GPU copy of one partial barrier producer and one uniform stencil consumer from a single pinned dual-function registration; not native Apple ICB.'}
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
