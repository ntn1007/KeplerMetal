#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit signed, isolated revocation witnesses and CPU-checked raw GPU data."""
import argparse,hashlib,json,struct,subprocess
from datetime import datetime
from pathlib import Path
HERE=Path(__file__).resolve().parent
BUILD='7aa93065ee56940e3788a5e2b3d1bebe1c0fdf2f44d03f1b6cc7418aada37b68'
CASES=['revoked-negative','native','revoked','native','revoked-negative','revoked']
SENTINEL=0xa5f0c3d2;VALUES={'native':0xdecafbad,'revoked':0x13579bdf}
def need(x,m):
 if not x:raise ValueError(m)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def capture(path,mode):
 data=Path(path).read_bytes();need(len(data)==4128*4,'capture length');words=struct.unpack('<4128I',data)
 need(all(x==SENTINEL for x in words[:16]+words[-16:]),'guard corruption')
 for i,x in enumerate(words[16:-16]):need(x==(SENTINEL if mode=='revoked-negative' else VALUES[mode]^i),'CPU oracle mismatch')
def classify(x,mode):
 need(x['mode']==mode and x['device_candidates']==1 and x['registry_id']==4294968416 and x['native_class']=='NVMTLCommandBuffer' and x['initial_status']==0 and x['initial_untouched'] and x['completed'] and x['late_revoke_refused'] and x['written'] and not x['errors'] and not x['guard_errors'] and not x['system_modified'],'host observation')
 revoked=mode!='native'
 for k in ('guard_installed','commit_blocked','enqueue_blocked','second_commit_blocked'):need(x[k] is revoked,'guard state '+k)
 need(x['stale_final_status']==(0 if revoked else 4) and x['dispatches']==(0 if mode=='revoked-negative' else 1),'status/dispatch')
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--runs',type=Path,nargs=6,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();b=a.build.resolve();need(not a.out.exists() and a.out.parent.is_dir() and len(set(a.runs))==6,'fresh output and distinct runs')
 need(sha(b/'inputs.json')==BUILD,'build identity');i=read(b/'inputs.json');need(i['GPU_dispatches']==0,'build dispatch')
 for n,h in i['frozen'].items():need(sha(b/n)==h,'frozen '+n)
 for n in ('host.mm','experiment.py'):need(sha(HERE/n)==i['frozen']['src/'+n],'source '+n)
 need(sha(b/'application')==i['application_SHA256'],'binary identity');intervals=[];pids=set();rows=[]
 for d,mode in zip(a.runs,CASES):
  d=d.resolve();inp=read(d/'inputs.json');manifest=read(d/'execution/manifest.json');lease=manifest['GPU_reservation'];x=read(d/'result.json');need(x==read(d/'execution/execution.stdout'),'raw result')
  need(inp['build_inputs_SHA256']==BUILD and inp['registry_id']==4294968416 and inp['mode']==mode and inp['profile']==i['profile'] and inp['application_SHA256']==i['application_SHA256'],'input profile')
  need(manifest['exit_code']==0 and not manifest['SIGKILL_requested'] and not manifest['authoritative_ps_status'] and lease['state']=='terminal' and lease['child_PID']==manifest['pid'] and lease['exit_code']==0 and not lease['known_signed_processes_live'] and manifest['pid'] not in pids and x['pid']==manifest['pid'],'terminal host');pids.add(manifest['pid']);intervals.append((datetime.fromisoformat(manifest['started_at']),datetime.fromisoformat(manifest['completed_at'])))
  need(sha(d/'application')==manifest['original_binary_sha256']==i['application_SHA256'] and sha(d/'execution/application')==manifest['signed_binary_sha256']==lease['signed_binary_sha256'],'signed binary');subprocess.run(['codesign','--verify','--strict',str(d/'execution/application')],check=True,capture_output=True)
  classify(x,mode);capture(d/'capture.bin',mode);rows.append({'mode':mode,'dispatches':x['dispatches'],'result_SHA256':sha(d/'result.json'),'capture_SHA256':sha(d/'capture.bin')})
 intervals.sort();need(all(a<=b for a,b in intervals) and all(x[1]<=y[0] for x,y in zip(intervals,intervals[1:])),'process overlap')
 out={'status':'PASS_BOUNDED_INSTANCE_REVOCATION','terminal_nonoverlapping_processes':6,'revoked_gpu_processes':2,'native_gpu_controls':2,'revoked_no_dispatch_controls':2,'revoked_gpu_words':8192,'native_gpu_words':8192,'negative_sentinel_words':8192,'guard_words':192,'build_inputs_SHA256':BUILD,'scope':'Process-local native command buffer instance, serialized ordinary Objective-C commit/enqueue sends. Not an ICB cancellation API, system driver fix, or protection against cached IMPs, runtime mutation or uncoordinated threads.','cases':rows}
 with a.out.open('x') as f:json.dump(out,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(out,sort_keys=True))
if __name__=='__main__':main()
