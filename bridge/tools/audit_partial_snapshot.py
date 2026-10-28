#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck partial CPU snapshots and regressions on the same runtime archive."""
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
 for name in ('snapshot','chain','barrier','uniform'):p.add_argument('--'+name,type=Path,nargs='+',required=True)
 p.add_argument('--current-source-build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'Fresh output required')
 paths=a.snapshot+a.chain+a.barrier+a.uniform;need(len(paths)==len({x.resolve() for x in paths})==18,'Eighteen distinct hosts required');rows=[];intervals=[];pids=set();archives=set();snapshot_verifiers={}
 for group,dirs,script in [('snapshot',a.snapshot,'verify_partial_snapshot.py'),('chain',a.chain,'verify_partial_range_chain.py'),('barrier',a.barrier,'verify_partial_chain_barrier.py'),('uniform',a.uniform,'verify_uniform_icb_3d.py')]:
  for raw in dirs:
   d=raw.resolve();inp=read(d/'inputs.json');m=read(d/'execution/manifest.json');archives.add(inp['runtime_archive_SHA256'])
   for name in ('KeplerCPUICB.mm','KeplerCPUICB.h','KeplerPartialGridPlan.h'):need(inp['frozen']['src/'+name]==sha(ROOT/'src'/name),'Runtime source differs: '+name)
   if group=='snapshot':
    need(inp['frozen']['src/partial_snapshot_probe.mm']==sha(ROOT/'tools/partial_snapshot_probe.mm'),'Probe source differs')
    v=(d/'src'/script).read_text();snapshot_verifiers[sha(d/'src'/script)]=v
    if inp['case_index'] in (1,2):need(sha(d/'src'/script)==sha(ROOT/'tools'/script),'Mixed verifier differs')
   else:need(inp['frozen']['src/'+script]==sha(ROOT/'tools'/script),'Regression verifier differs')
   proc=subprocess.run([sys.executable,'-I',str(d/'src'/script),str(d)],capture_output=True,text=True,timeout=120);need(proc.returncode==0,'Verifier failed: '+str(d)+' '+proc.stderr[-1200:]);v=json.loads(proc.stdout);need(v==json.loads((d/'verification.stdout').read_text()) and v.get('status',v.get('verification'))=='PASS','Recorded verifier differs');rows.append((group,inp,v,d))
   need(m['pid'] not in pids,'Duplicate PID');pids.add(m['pid']);intervals.append((datetime.fromisoformat(m['started_at']),datetime.fromisoformat(m['completed_at'])))
 need(len(archives)==1,'Runtime archive differs');current=(ROOT/'tools/verify_partial_snapshot.py').read_text();need(1<=len(snapshot_verifiers)<=2 and current in snapshot_verifiers.values(),'Unexpected verifier versions')
 if len(snapshot_verifiers)==2:
  old=next(x for x in snapshot_verifiers.values() if x!=current)
  updated=old.replace("snap['source_records_prepared']==(16 if scenario==3 else 4)","snap['source_records_prepared']==(16 if scenario==3 else 3 if scenario in (1,2) else 4)").replace("tuple(x+snap['materials_at_snapshot'] for x in expected_materials[trial])","tuple(x+snap['materials_at_snapshot']-(1 if scenario in (1,2) and x>0 else 0) for x in expected_materials[trial])").replace("'snapshot_cache_rematerialized':True","'partial_cache_rematerialized':True,'uniform_cache_reused':scenario in (1,2)")
  need(updated==current,'Earlier verifier changes differ from mixed-case qualification')
 tested=read(rows[0][3]/'archive-manifest.json');fresh=read(a.current_source_build/'manifest.json');need(fresh['status']=='PASS' and len(tested['object_SHA256'])==7 and tested['object_SHA256']==fresh['object_SHA256'] and tested['source_SHA256']==fresh['source_SHA256'],'Independent rebuild differs')
 for name,digest in fresh['source_SHA256'].items():need(sha(ROOT/'src'/name)==digest and sha(a.current_source_build/'src'/name)==digest,'Fresh source differs: '+name)
 for archive in (rows[0][3]/'runtime_archive.a',a.current_source_build/'libKeplerMetal.a'):
  for name,digest in tested['object_SHA256'].items():need(hashlib.sha256(subprocess.run(['xcrun','ar','-p',str(archive),name],check=True,capture_output=True).stdout).hexdigest()==digest,'Object differs: '+name)
 snapshots=[r[2] for r in rows if r[0]=='snapshot'];names=('partial_partial','partial_uniform','uniform_partial','partial_partial_3d_limit');need(Counter(x['scenario'] for x in snapshots if x['mode']=='prepare')==Counter({n:1 for n in names}) and Counter(x['scenario'] for x in snapshots if x['mode']=='execute')==Counter({n:2 for n in names}),'Snapshot coverage differs')
 barriers=[r[2] for r in rows if r[0]=='barrier'];uniform=[r[2] for r in rows if r[0]=='uniform'];chain=[r[2] for r in rows if r[0]=='chain'];need({x['case'] for x in barriers}=={0,6} and {x['form'] for x in uniform}=={'groups','threads'} and {x['scenario'] for x in chain}=={'partial_partial','partial_partial_3d_limit'},'Regression coverage differs')
 intervals.sort();need(all(x<=y for x,y in intervals) and all(x[1]<=y[0] for x,y in zip(intervals,intervals[1:])),'Host intervals overlap')
 result={'status':'PASS','host_processes':len(rows),'nonoverlapping':True,'runtime_archive_SHA256':next(iter(archives)),'fresh_archive_SHA256':fresh['static_library_SHA256'],'fresh_object_members_match':True,'snapshot_verifier_versions':sorted(snapshot_verifiers),'snapshot_logical_dispatches':sum(x['logical_dispatches'] for x in snapshots),'snapshot_invocations':sum(x['invocations'] for x in snapshots),'snapshot_checked_output_words':sum(x['checked_output_words'] for x in snapshots),'snapshot_negative_observations':sum(x['negative_preflight_controls'] for x in snapshots),'snapshot_order_controls':sum(x['order_controls'] for x in snapshots),'barrier_regression_invocations':sum(x['threads'] for x in barriers),'uniform_regression_invocations':sum(x['GPU_invocations_counted'] for x in uniform),'chain_regression_invocations':sum(x['invocations'] for x in chain),'source_SHA256':{n:sha(ROOT/'src'/n) for n in ('KeplerCPUICB.mm','KeplerCPUICB.h','KeplerPartialGridPlan.h')},'scope':'Explicit CPU snapshot copies of certified project partial-grid commands; no native Apple ICB or system-wide integration.'}
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
