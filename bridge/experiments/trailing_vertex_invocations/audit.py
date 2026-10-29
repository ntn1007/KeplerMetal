#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check two native GTX process receipts and two transferred M1 summaries."""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parents[1]/'experiments/cas_divergence'))
from run_repair import SYSTEM

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def need(ok,why):
    if not ok:raise ValueError(why)
def sign(p):need(subprocess.run(['codesign','--verify','--strict',str(p)],capture_output=True).returncode==0,'signature differs')
def report(path,device):
    obj=load(path);need(obj['device']==device and obj['registry_id']!=0,'device differs')
    need(obj['reflection']==[{'access':1,'active':True,'name':'seen','type':0,'index':0}],'reflection differs')
    need(obj['results']==[{'count':n,'mask':m,'guards':True,'completed':True} for n,m in ((0,0),(3,7),(4,7),(5,7))],'observation differs')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('build','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--runs',type=Path,nargs=2,required=True);p.add_argument('--m1',type=Path,nargs=2,required=True);a=p.parse_args()
    need(not a.out.exists() and a.out.parent.is_dir() and len(set(a.runs))==2 and len(set(a.m1))==2,'fresh output / distinct runs')
    b=load(a.build/'build.json');need(b['status']=='PREPARED_ONLY' and not b['gpu_execution'] and b['system']==SYSTEM,'build differs')
    for n,h in b['files_sha256'].items():need(sha(a.build/n)==h,'build file differs')
    need(sha(HERE/'client.mm')==sha(a.build/'client.mm')=='3e3bf0b04d4b9e600b71c9a8dd3b630f418c317330f41129e8bbab788f1f9d2d','source differs');sign(a.build/'application')
    intervals=[];rows=[]
    for root in a.runs:
        m=load(root/'manifest.json');lease=m['reservation'];need(m['status']=='TERMINAL' and m['exit_code']==0 and m['build_sha256']==sha(a.build/'build.json') and m['host_sha256']==sha(root/'application')==b['files_sha256']['application'] and m['runner_sha256']==sha(HERE/'experiment.py'),'process differs')
        need(lease['state']=='terminal' and lease['child_PID']==m['pid'] and lease['exit_code']==0 and lease['child_birth_observed'] and not lease['SIGKILL_requested'] and not lease['authoritative_ps_status'],'lease differs')
        need(m['system_before']==m['system_after']==SYSTEM and m['stdout_sha256']==sha(root/'stdout.json') and m['stderr_sha256']==sha(root/'stderr.log'),'logs differ');sign(root/'application');report(root/'stdout.json','NVIDIA GeForce GTX 880M');intervals.append((m['started_at'],m['completed_at']));rows.append({'manifest_sha256':sha(root/'manifest.json'),'stdout_sha256':sha(root/'stdout.json')})
    intervals.sort();need(all(x<=y for x,y in intervals) and intervals[0][1]<=intervals[1][0],'overlapping GPU runs')
    m1pin='661c06a36aa7b99328b9460d1aba1e573582ba084b1a652af1c1aee73c7ff30b'
    for path in a.m1:need(sha(path)==m1pin,'M1 capture differs');report(path,'Apple M1 Max')
    out={'status':'PASS_NATIVE_VERTEX_WRITE_WITNESS','source_sha256':sha(HERE/'client.mm'),'gtx_runs':rows,'m1_capture_sha256':m1pin,'m1_host_binary_sha256_observed':'e2db28ff2caf32655328d59e2e54748163746962989adeb02ff02040ecc3c133','m1_os_observed':'27.2 (26B123)','counts':[0,3,4,5],'observed_masks':[0,7,7,7],'gpu_processes_gtx':2,'reference_runs_m1':2,'guards_intact':True,'trailing_invocation_proved':False,'adapter_tested':False,'performance_benchmark':False,'system_files_checked_unchanged':True}
    with a.out.open('x') as f:json.dump(out,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(out))
if __name__=='__main__':main()
