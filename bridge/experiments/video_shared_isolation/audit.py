#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the type-6 shared-client isolation experiment without running a host."""
import argparse, hashlib, json, struct, subprocess
from datetime import datetime
from pathlib import Path
HERE=Path(__file__).resolve().parent
BUILD_SHA='0ebfda3dc643e49191aa683e9927ac75fc69100429169a28cc7476cb99564517'
GPU_ID=4294968416
CASES=[('none-1',False,False,False),('shared-1',False,False,True),('pair-1',True,False,True),('attach-1',True,True,False),('attach-2',True,True,False),('pair-2',True,False,True),('shared-2',False,False,True),('none-2',False,False,False)]
SENTINEL=0xa5f0c3d2

def need(x,msg):
 if not x:raise ValueError(msg)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def check_words(path,seed,skip):
 raw=Path(path).read_bytes();need(len(raw)==(4096+32)*4,'capture length');v=struct.unpack('<4128I',raw)
 need(all(x==SENTINEL for x in v[:16]+v[-16:]),'guards')
 for index,value in enumerate(v[16:-16]):need(value==(SENTINEL if skip else ((index*1664525)&0xffffffff)^seed),'GPU/CPU comparison')
 return len(v)-32

def check_phase(x, *, failure, skip):
 for k in ('attempted','library','function','pipeline'):need(x[k] is True,'phase '+k)
 need(x['queue'] is not failure and x['buffer'] is not failure and x['written'] is not failure,'phase queue or capture')
 need(x['submitted'] is (not skip and not failure) and x['completed'] is (not skip and not failure),'dispatch status')
 need(x['errors']==0 and x['guard_errors']==0,'internal errors')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--hosts',type=Path,nargs=8,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();b=a.build.resolve();need(not a.out.exists() and a.out.parent.is_dir() and len(set(a.hosts))==8,'fresh output and distinct hosts')
 need(sha(b/'inputs.json')==BUILD_SHA,'build identity');i=read(b/'inputs.json')
 for n,h in i['frozen'].items():need(sha(b/n)==h,'build changed '+n)
 for n in ('coordinator.py','video_provider_fields_observer.mm','video_provider_gate_main.mm','video_provider_lookup_client.mm','ComputeWitness.mm','ComputeWitness.h'):need(sha(HERE/n)==i['frozen']['src/'+n],'source changed '+n)
 for n in ('VideoContextLease.cpp','VideoContextLease.h'):need(sha(HERE.parent/'video_context_lease'/n)==i['frozen']['src/'+n],'lease source changed')
 need(i['GPU_registry_ID']==GPU_ID,'GPU profile');rows=[];intervals=[];pids=set();gpuwords=0;negativewords=0;guards=0
 for d,(label,probe,attach,pair) in zip(a.hosts,CASES):
  skip=True;failure=pair or attach
  d=d.resolve();inp=read(d/'inputs.json');m=read(d/'execution/manifest.json');l=m['GPU_reservation'];g=read(d/'provider-gate.json');result=read(d/'result.json')
  need(inp['build_manifest_SHA256']==BUILD_SHA and inp['mode']=='hardware' and inp['route']=='enabled' and inp['probe'] is probe and inp['attach'] is attach and inp['compute'] is True and inp['skip'] is skip and inp['pair'] is pair,'case configuration')
  for n,h in inp['assets_SHA256'].items():need(sha(d/'assets'/n)==h,'asset '+n)
  need(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and l['state']=='terminal' and l['child_PID']==m['pid'] and l['exit_code']==0 and not l['known_signed_processes_live'],'terminal process')
  need(m['pid'] not in pids,'pid');pids.add(m['pid']);intervals.append((datetime.fromisoformat(m['started_at']),datetime.fromisoformat(m['completed_at'])))
  need(sha(d/'application')==m['original_binary_sha256']==i['frozen']['application'] and sha(d/'execution/application')==m['signed_binary_sha256']==l['signed_binary_sha256'],'binary')
  subprocess.run(['codesign','--verify','--strict',str(d/'execution/application')],capture_output=True,check=True)
  need(g==read(d/'outputs/provider-gate.json') and result==read(d/'execution/execution.stdout'),'outputs')
  need(g['status']=='COMPLETE' and g['calibration_pass'] and g['service_calibration_pass'] and not g['failure_output_unowned'] and g['gate_calls']==1 and not g['sierra_loaded'] and not g['sierra_export_called'],'gate')
  o=g['argument_observation'];need(o['caller_pinned'] and o['selected_service_registry_ok'] and o['selected_service_registry_ID']==GPU_ID and g['metal_registry_matches'],'service identity')
  need(g['context_open_attempts']==int(probe) and g['context_close_attempts']==int(probe) and g['shared_open_attempts']==int(attach) and g['shared_close_attempts']==int(attach) and g['association_attempts']==int(attach),'context operations')
  if probe:need(g['context_open_status']==0 and g['context_close_status']==0,'context result')
  if attach:need(g['shared_open_status']==0 and g['shared_close_status']==0 and g['association_status']==0 and g['connections_distinct'],'association result')
  need(g['pair_open_attempts']==int(pair) and g['pair_close_attempts']==int(pair),'pair operations')
  if pair:need(g['pair_open_status']==0 and g['pair_close_status']==0 and g['pair_distinct'],'pair result')
  v=result['public_decode'];need(v['decode']['specification']['RequireHardwareAcceleratedVideoDecoder'] is True and v['decode']['create_status']==-12913 and v['output_frames']==0,'video outcome')
  before=g['compute_before'];after=g['compute_after'];check_phase(before,failure=False,skip=skip);check_phase(after,failure=failure,skip=skip)
  need(g['explicit_gpu_dispatches_by_gate']==0 and g['explicit_video_external_methods']==0,'dispatch count')
  for phase,seed,exists in [('before',0x12345678,True),('after',0x87654321,not failure)]:
   path=d/'outputs'/f'{phase}-compute.bin';need(path.exists()==exists,'capture presence')
   if exists:
    count=check_words(path,seed,skip);guards+=32
    if skip:negativewords+=count
    else:gpuwords+=count
  rows.append({'case':label,'probe':probe,'attach':attach,'pair':pair,'skip_dispatch':skip,'after_queue_created':not failure,'before_capture_SHA256':sha(d/'outputs/before-compute.bin')})
 intervals.sort();need(all(a<=b for a,b in intervals) and all(x[1]<=y[0] for x,y in zip(intervals,intervals[1:])),'overlapping hosts')
 out={'status':'EXPECTED_FAILURE_CONFIRMED','build_SHA256':BUILD_SHA,'terminal_nonoverlapping_processes':8,'no_dispatch_sentinel_words':negativewords,'guard_words':guards,'no_client_after_queue_successes':2,'shared_only_after_queue_failures':2,'unassociated_pair_after_queue_failures':2,'associated_pair_after_queue_failures':2,'hardware_video_frames':0,'cases':rows,'scope':'Controlled process-local legacy AppleGVA path. Opening and closing type-6 alone is sufficient to reproduce a subsequent Metal queue creation failure in the tested setup; underlying cause and broader scope unknown.'}
 with a.out.open('x') as f:json.dump(out,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(out,sort_keys=True))
if __name__=='__main__':main()
