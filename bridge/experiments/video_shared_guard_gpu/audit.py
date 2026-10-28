#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit shared-connection ownership and actual post-release GPU results."""
import argparse,hashlib,json,struct,subprocess
from datetime import datetime
from pathlib import Path
HERE=Path(__file__).resolve().parent
BUILD='52762a5076d74a64b98d42f51d07feed86930e7878babb835f10936915307d5d'
CASES=['observe','compare','release','release-negative','release-negative','release','compare']
SENTINEL=0xa5f0c3d2;SEED=0x12345678

def need(x,msg):
 if not x:raise ValueError(msg)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def check_capture(path,skip):
 raw=Path(path).read_bytes();need(len(raw)==4128*4,'capture size');words=struct.unpack('<4128I',raw)
 need(all(w==SENTINEL for w in words[:16]+words[-16:]),'guards')
 for i,w in enumerate(words[16:-16]):need(w==(SENTINEL if skip else ((i*1664525)&0xffffffff)^SEED),'capture oracle')

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--runs',type=Path,nargs=7,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();b=a.build.resolve();need(not a.out.exists() and a.out.parent.is_dir() and len(set(a.runs))==7,'fresh output/distinct runs')
 need(sha(b/'inputs.json')==BUILD,'build identity');i=read(b/'inputs.json');need(i['GPU_dispatches']==0,'build dispatch')
 for n,h in i['frozen'].items():need(sha(b/n)==h,'frozen '+n)
 for n in ('host.mm','observer.mm','experiment.py','ComputeWitness.mm','ComputeWitness.h'):need(sha(HERE/n)==i['frozen']['src/'+n],'source '+n)
 need(sha(HERE.parent/'video_shared_guard/SharedAliasGuard.h')==i['frozen']['src/SharedAliasGuard.h'],'guard source')
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
  c=identity['connection_comparison'];need(x['queue_before'] is True and x['queue_after'] is (mode!='compare'),'queue status')
  if mode=='observe':need(c['status']=='NOT_REQUESTED','control')
  else:
   for k in ('profile_pinned','metal_send_before','extra_nonnull','port_names_equal','metal_self_equal','extra_self_equal','object_equal','metal_send_after'):need(c[k] is True,'connection '+k)
   need(c['status']=='OBSERVED' and c['extra_open_status']==0 and c['extra_close_status']==0 and c['explicit_video_selectors']==0,'IOKit status')
   need(c['refs_before_status']==c['refs_opened_status']==c['refs_after_status']==0 and c['refs_before']==1 and c['refs_opened']==2 and c['refs_after']==1,'send-right references')
   release=mode.startswith('release');need(c['release_only'] is release and c['release_qualified'] is release and c['extra_close_uses_same_port_name'] is (not release),'release mode')
   need(c['metal_service_before_status']==-536870201 and c['extra_service_status']==-536870201 and c['metal_service_after_status']==(-536870201 if release else -536870206),'service status')
  w=x['gpu_witness'];skip=mode=='release-negative';run=mode!='compare';need(w['attempted'] is run,'witness attempted')
  path=d/'gpu-compute.bin'
  if run:
   need(all(w[k] for k in ('library','function','pipeline','queue','buffer','written')) and w['submitted'] is (not skip) and w['completed'] is (not skip) and w['errors']==0 and w['guard_errors']==0 and path.exists(),'witness result')
   need(x['explicit_GPU_dispatches']==int(not skip),'dispatch count');check_capture(path,skip);guards+=32
   if skip:negative+=4096
   else:gpu+=4096
  else:need(not path.exists() and x['explicit_GPU_dispatches']==0,'failure unexpectedly dispatched')
  rows.append({'mode':mode,'queue_after':x['queue_after'],'gpu_dispatched':bool(x['explicit_GPU_dispatches']),'result_SHA256':sha(d/'result.json')})
 intervals.sort();need(all(a<=b for a,b in intervals) and all(x[1]<=y[0] for x,y in zip(intervals,intervals[1:])),'overlap')
 out={'status':'PASS_BOUNDED_REFERENCE_RELEASE','terminal_nonoverlapping_processes':7,'release_gpu_processes':2,'reference_release_negative_controls':2,'explicit_close_expected_queue_failures':2,'gpu_verified_words':gpu,'negative_sentinel_words':negative,'guard_words':guards,'same_object_and_name':True,'send_right_counts':[1,2,1],'build_inputs_SHA256':BUILD,'hardware_video_execution_proved':False,'scope':'Pinned process-local GPU/Metal shared alias; reusable guard and IOConnectRelease after verified extra send-right reference. Not a video decoder or general driver fix.','cases':rows}
 with a.out.open('x') as f:json.dump(out,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(out,sort_keys=True))
if __name__=='__main__':main()
