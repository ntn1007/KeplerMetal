#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit shared-connection ownership and actual post-release GPU results."""
import argparse,hashlib,json,struct,subprocess
from datetime import datetime
from pathlib import Path
HERE=Path(__file__).resolve().parent
BUILD='34df9fb140ab09155f0ca2c78ee72364bc078ef3b948b1a95cdd107509f9ed9a'
CASES=['control','pending','control-negative','pending-negative','pending','control','pending-negative']
SENTINEL=0xa5f0c3d2;SEED=0x12345678

def need(x,msg):
 if not x:raise ValueError(msg)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def check_capture(path,skip):
 raw=Path(path).read_bytes();need(len(raw)==4128*4,'capture size');words=struct.unpack('<4128I',raw)
 need(all(w==SENTINEL for w in words[:16]+words[-16:]),'guards')
 for i,w in enumerate(words[16:-16]):need(w==(SENTINEL if skip else ((i*1664525)&0xffffffff)^SEED),'capture oracle')

def check_pending(before,after,final,skip):
 for stage in (before,after):
  need(stage['command_status'] in (2,3) and stage['gate_value']==0 and stage['watchdog_state']==0 and stage['changed_words']==0,'pending witness')
 need(final['normal_signal'] and final['watchdog_state']==1 and final['gate_value']==1 and final['command_status']==4 and final['dispatch_encoded'] is (not skip) and not final['errors'] and not final['guard_errors'] and final['written'],'completion')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--runs',type=Path,nargs=7,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();b=a.build.resolve();need(not a.out.exists() and a.out.parent.is_dir() and len(set(a.runs))==7,'fresh output/distinct runs')
 need(sha(b/'inputs.json')==BUILD,'build identity');i=read(b/'inputs.json');need(i['GPU_dispatches']==0,'build dispatch')
 for n,h in i['frozen'].items():need(sha(b/n)==h,'frozen '+n)
 for n in ('host.mm','observer.mm','experiment.py','ComputeWitness.mm','ComputeWitness.h','PendingWitness.mm','PendingWitness.h'):need(sha(HERE/n)==i['frozen']['src/'+n],'source '+n)
 need(sha(HERE.parent/'video_shared_guard/SharedAliasGuard.h')==i['frozen']['src/SharedAliasGuard.h'],'guard source')
 for n in ('VideoContextLease.h','VideoContextLease.cpp'):need(sha(HERE.parent/'video_context_lease'/n)==i['frozen']['src/'+n],'lease source '+n)
 for n in ('GuardedAliasBackend.h','GuardedAliasBackend.cpp'):need(sha(HERE.parent/'video_guarded_backend'/n)==i['frozen']['src/'+n],'backend source '+n)
 need(sha(b/'application')==i['application_SHA256'] and sha(b/'libObjectObserver.dylib')==i['observer_SHA256'],'binary frozen')
 subprocess.run(['codesign','--verify','--strict',str(b/'libObjectObserver.dylib')],check=True,capture_output=True)
 intervals=[];pids=set();rows=[];gpu=0;negative=0;guards=0
 for d,mode in zip(a.runs,CASES):
  d=d.resolve();inp=read(d/'inputs.json');m=read(d/'execution/manifest.json');l=m['GPU_reservation'];x=read(d/'result.json');need(x==read(d/'execution/execution.stdout'),'raw result')
  need(inp['build_inputs_SHA256']==BUILD and inp['registry_id']==4294968416 and inp['mode']==mode and inp['profile']==i['profile'] and inp['application_SHA256']==i['application_SHA256'] and inp['observer_SHA256']==i['observer_SHA256'],'input profile')
  need(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and l['state']=='terminal' and l['child_PID']==m['pid'] and l['exit_code']==0 and not l['known_signed_processes_live'] and m['pid'] not in pids,'terminal host');pids.add(m['pid']);intervals.append((datetime.fromisoformat(m['started_at']),datetime.fromisoformat(m['completed_at'])))
  need(sha(d/'application')==m['original_binary_sha256']==i['application_SHA256'] and sha(d/'execution/application')==m['signed_binary_sha256']==l['signed_binary_sha256'],'host binary');subprocess.run(['codesign','--verify','--strict',str(d/'execution/application')],check=True,capture_output=True)
  need(x['pid']==m['pid'] and x['mode']==mode and x['status']=='OBSERVATION_COMPLETED' and x['registry_id']==4294968416 and x['metal_candidates']==1 and x['buffer_CPU_correct'] and x['buffer_CPU_after_context_correct'] and not x['hardware_video_execution_proved'],'host result')
  o=x['observation'];need(o['matching_nonnull']==o['matching_type']==o['shared_matching_argument']==o['shared_nonnull']==o['shared_type_matches']==o['shared_stored_device_matches']==1 and o['return_unchanged'] and not o['shared_failures'] and not o['context_attempts'],'shared object provenance')
  identity=x['resource_identity'];need(identity['resource_shared_matches'] and identity['resource_shared_after'] and identity['getter_called'] is False and identity['status']=='PINNED','resource relationship')
  c=identity['connection_comparison'];need(x['queue_before'] is True and x['queue_after'] is True,'queue status')
  if mode.startswith('control'):need(c['status']=='NOT_REQUESTED','control')
  else:
   for k in ('started','closed','release_qualified','connections_distinct','port_names_equal','metal_self_equal','extra_self_equal','object_equal'):need(c[k] is True,'lease '+k)
   need(not c['rejected'] and not c['failure_output_unowned'] and not c['unreleased'] and not c['postcondition_failed'] and c['status']=='OBSERVED' and not c['system_modified'] and c['explicit_video_selectors']==0,'qualification')
   for k in ('context_open_status','shared_open_status','association_status','context_close_status','shared_close_status','refs_before_status','refs_opened_status','refs_before_close_status','refs_after_status'):need(c[k]==0,'status '+k)
   need([c['refs_before'],c['refs_opened'],c['refs_before_close'],c['refs_after']]==[1,2,2,1],'send-right refs')
   need(c['release_only'] is True,'release mode')
  before=x['pending_before'];after=x['pending_after'];final=x['pending_final'];skip=mode.endswith('negative')
  check_pending(before,after,final,skip)
  path=d/'pending-compute.bin';need(path.exists() and x['explicit_GPU_dispatches']==int(not skip),'dispatch evidence');check_capture(path,skip);guards+=32
  if skip:negative+=4096
  else:gpu+=4096
  rows.append({'mode':mode,'pending_before':before['command_status'],'pending_after':after['command_status'],'gpu_dispatched':bool(x['explicit_GPU_dispatches']),'result_SHA256':sha(d/'result.json')})
 intervals.sort();need(all(a<=b for a,b in intervals) and all(x[1]<=y[0] for x,y in zip(intervals,intervals[1:])),'overlap')
 out={'status':'PASS_BOUNDED_PENDING_METAL_COMMAND','terminal_nonoverlapping_processes':7,'lease_gpu_processes':2,'lease_nodispatch_controls':2,'no_lease_gpu_processes':2,'no_lease_nodispatch_controls':1,'gpu_verified_words':gpu,'negative_sentinel_words':negative,'guard_words':guards,'same_object_and_name_for_lease':True,'send_right_counts':[1,2,1],'build_inputs_SHA256':BUILD,'hardware_video_execution_proved':False,'scope':'A submitted command remained gated and incomplete while a video lease was associated and released, then completed on GTX. No proof of simultaneous GPU execution, video decode, general driver repair or uncoordinated concurrency.','cases':rows}
 with a.out.open('x') as f:json.dump(out,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(out,sort_keys=True))
if __name__=='__main__':main()
