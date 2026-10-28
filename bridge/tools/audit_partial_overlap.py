#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit overlapping partial ICB snapshots against independent prior runs."""
import argparse, hashlib, json, subprocess, sys
from collections import Counter
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def need(v,why):
 if not v:raise ValueError(why)
def run_verifier(d,script):
 p=subprocess.run([sys.executable,'-I',str(d/'src'/script),str(d)],capture_output=True,text=True,timeout=120)
 need(p.returncode==0,'Oracle failed: '+str(d)+' '+p.stderr[-1000:]);r=json.loads(p.stdout);need(r==read(d/'verification.stdout') and r['status']=='PASS','Recorded oracle differs');return r
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--overlap',type=Path,nargs=6,required=True);p.add_argument('--reference',type=Path,nargs=2,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
 paths=[x.resolve() for x in a.overlap];refs=[x.resolve() for x in a.reference];need(len(set(paths+refs))==8 and not a.out.exists() and a.out.parent.is_dir(),'Distinct paths and fresh output required')
 snapshots={};archives=set();rows=[];intervals=[];pids=set()
 for d in refs:
  result=run_verifier(d,'verify_partial_snapshot.py');i=read(d/'inputs.json');need(i['case_index'] in (0,3) and result['mode']=='execute' and i['case_index'] not in snapshots,'Reference coverage differs');snapshots[i['case_index']]=d;archives.add(i['runtime_archive_SHA256'])
 for d in paths:
  i=read(d/'inputs.json');m=read(d/'execution/manifest.json');archives.add(i['runtime_archive_SHA256'])
  for name in ('KeplerCPUICB.mm','KeplerCPUICB.h','KeplerPartialGridPlan.h'):need(i['frozen']['src/'+name]==sha(ROOT/'src'/name),'Runtime source differs: '+name)
  for name in ('partial_overlap.py','partial_overlap_probe.mm','verify_partial_overlap.py'):need(i['frozen']['src/'+name]==sha(ROOT/'tools'/name),'Test source differs: '+name)
  subprocess.run(['codesign','--verify','--strict',str(d/'execution/application')],check=True,capture_output=True)
  result=run_verifier(d,'verify_partial_overlap.py');need(m['pid'] not in pids,'Duplicate PID');pids.add(m['pid']);intervals.append((datetime.fromisoformat(m['started_at']),datetime.fromisoformat(m['completed_at'])))
  compared=0
  if result['mode']=='execute':
   reference=snapshots[i['case_index']]/'outputs';current=d/'outputs';files=sorted(x.name for x in current.iterdir());need(files==sorted(x.name for x in reference.iterdir()),'Reference file set differs')
   for name in files:need((current/name).read_bytes()==(reference/name).read_bytes(),'Reference output differs: '+name);compared+=1
  rows.append({'scenario':i['case_index'],'mode':result['mode'],'direction':result['same_buffer_overlap_direction'],'invocations':result['invocations'],'logical_dispatches':result['logical_dispatches'],'checked_output_words':result['checked_output_words'],'reference_identical_files':compared,'result_SHA256':sha(d/'results.json')})
 need(len(archives)==1,'Runtime archives differ');need(Counter((x['scenario'],x['mode']) for x in rows)==Counter({(0,'prepare'):1,(3,'prepare'):1,(0,'execute'):2,(3,'execute'):2}),'Coverage differs')
 intervals.sort();need(all(x<=y for x,y in intervals) and all(x[1]<=y[0] for x,y in zip(intervals,intervals[1:])),'Host intervals overlap')
 result={'status':'PASS','host_processes':len(rows),'nonoverlapping':True,'runtime_archive_SHA256':next(iter(archives)),'logical_dispatches':sum(x['logical_dispatches'] for x in rows),'invocations':sum(x['invocations'] for x in rows),'checked_output_words':sum(x['checked_output_words'] for x in rows),'reference_identical_files':sum(x['reference_identical_files'] for x in rows),'directions':['forward','backward'],'rows':rows,'scope':'CPU snapshot overlapping ranges of the same project ICB; not a GPU-timeline copy or native Apple ICB.'}
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps({k:v for k,v in result.items() if k!='rows'},sort_keys=True))
if __name__=='__main__':main()
