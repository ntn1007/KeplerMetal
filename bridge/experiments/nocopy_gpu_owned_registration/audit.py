#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit coverage observations from real Metal buffers; no GPU work here."""
import argparse,copy,hashlib,json,subprocess,sys
from collections import Counter
from datetime import datetime
from pathlib import Path
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent/'video_context_object'))
from audit import manifest_check

def need(v,s):
 if not v:raise ValueError(s)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def check(r,mode,rid):
 is_nc=mode in ('nocopy-gpu','nocopy-repair-gpu','nocopy-reject-gpu','nocopy-repair-gpu-late');repaired=mode in ('nocopy-repair-gpu','nocopy-repair-gpu-late');late=mode=='nocopy-repair-gpu-late';gpu='-gpu' in mode
 need(r['registration_owner_released'] is gpu and r['registration_duplicate_refused'] is gpu and r['registration_late_refused'] is gpu,'Registration refusals')
 need(r['tracked_registered']==(2 if gpu else 0) and r['tracked_completed']==(2 if gpu else 0) and r['tracked_failures']==0 and r['tracked_unexpected']==0,'Registered GPU work')
 need(r['client_block_distinct'] and r['client_block_retained'] and r['client_library_bound'] and r['client_calls']==(1 if repaired else 0) and r['client_rejected']==0 and r['client_status']==(0 if repaired else -1),'Separate client callback')
 need(r['mode']==mode and r['registry_id']==rid and r['status']=='OBSERVATION_COMPLETED' and r['metal_candidates']==1 and r['buffer_CPU_correct'] and r['keeper_CPU_correct_after'] and r['vm_control'] and r['explicit_GPU_dispatches']==(2 if gpu else 0) and not r['hardware_video_execution_proved'],'Host result')
 need((r['gpu_precommit_weak_alive'] if gpu else not r['gpu_precommit_weak_alive']) and r['gpu_precommit_callbacks']==0,'Queued buffer lifetime')
 need(r['gpu_handler_count']==(2 if gpu else 0) and r['gpu_handler_status']==(4 if gpu else 0),'GPU completion handler')
 need(r['gpu_requested'] is gpu and r['gpu_completed'] is gpu and r['gpu_status']==(4 if gpu else 0) and r['gpu_mismatches']==0,'GPU witness status')
 need(r['gpu_second_status']==(4 if gpu else 0) and r['gpu_after_first_callbacks']==0 and (r['gpu_second_at_first_wait'] in (2,3,4) if gpu else r['gpu_second_at_first_wait']==0),'Second queue status')
 words=r['gpu_words'];need(len(words)==(8192 if gpu else 0),'GPU witness size')
 if gpu:
  for n,v in enumerate(words):
   q,i=divmod(n,4096);need(v==((i*13+7)&255)*3+i+(0x1234 if q else 0),'Independent GPU output oracle')
 x=r['observation'];need(x['create_calls']==x['matching_nonnull']==x['matching_type']==1 and x['shared_calls']==x['shared_nonnull']==x['shared_type_matches']==x['shared_stored_device_matches']==1 and x['return_unchanged'] and x['type_or_profile_failures']==x['registry_query_failures']==x['context_attempts']==0,'Device/shared identity')
 for key in ('resource_a','resource_b'):
  y=r[key];need(y['status']=='PINNED' and y['resource_shared_matches'] and y['slot_read'] and y['resource_nonnull'] and not y['getter_called'] and y['resource_slot_offset']==136,'Resource identity')
 for key in ('before_a','after_a','before_b'):
  y=r[key];need(y['snapshot_valid'] and y['first_nonzero'] and y['second_nonzero'] and y['first_range_covered']==1 and y['second_range_covered']==1,'Coverage')
 c=r['resource_calibration'];need(r['release_control'] and c['pinned'] and c['type_matches'] and c['balanced'] and c['intercepted']==1 and r['timeline'][0]['cf_releases']==(1 if is_nc else 0),'Release calibration')
 need(r['hooks_installed'] and r['hooks_restored'],'ObjC hook state')
 n=0 if mode=='hold-nocopy' else 1;entry=1 if is_nc else 0
 need(r['resource_a']['actual_class']=='NVMTLBuffer' and r['resource_a']['actual_superclass']=='MTLIOAccelBuffer' and r['resource_a']['selected_dealloc_is_hook'],'Concrete class')
 need(r['nv_dealloc_calls']==r['branch_inputs_read']==r['root_branch_candidate']==n and r['buffer_dealloc_calls']==r['resource_dealloc_calls']==r['resource_field_matches']==0 ,'Dealloc observations')
 need(r['resource_calibration']['entries']==1,'Wrapper entry calibration')
 need(r['weak_control'] and r['hold_correct'] and r['super_control'] and r['nocopy_deallocator_bad_args']==0,'Weak, hold, deallocator or synthetic super control')
 need(r['first_buffer_weak_nil'] is (mode!='hold-nocopy'),'Weak observation differs')
 t=r['timeline'];need(len(t)==4 and [x['target_ms'] for x in t]==[0,250,1000,3000],'Timeline layout')
 for i,x in enumerate(t):
  need(x['elapsed_ms']>=x['target_ms'] and x['entry_calls']==entry and x['metal_callers']==entry and x['cf_releases']==entry and x['bad_args']==0,'Timeline observation')
  need(x['deallocator_calls']==(1 if repaired else 0) and x['freed'] is repaired,'Callback state')
  if i:need(x['elapsed_ms']>=t[i-1]['elapsed_ms'] and x['deallocator_calls']>=t[i-1]['deallocator_calls'],'Timeline ordering')
 order=r['release_order']
 if is_nc:
  need(order['method_calls']==order['method_shape']==order['port_matches']==order['id_matches']==1 and order['method_status']==0,'Native release method')
  need(0<order['outer_start']<order['method_start']<order['method_end']<order['tail']<order['outer_end']<order['root'],'Release order')
 else:
  need(order['method_calls']==0 and order['method_start']==order['method_end']==0,'Unexpected native release method')
 need(r['nested_control'],'Nested release calibration')
 need(r['nested_resource_finalizer_tail']==(1 if is_nc else 0) and r['watched_cf_release_returns']==(1 if is_nc else 0),'Nested resource finalizer observation')
 need(r['root_stub_pinned'] and r['root_binding_read'] and r['root_binding_interposed'] and not r['root_binding_original'],'Root import binding')
 need(r['root_matches']==(0 if mode=='hold-nocopy' else 1),'Root trace count')
 need(r['block_ivar_pinned'] and r['block_ivar_offset']==320 and r['block_before_read'],'Block field metadata')
 hasblock=is_nc or mode=='hold-nocopy'
 need(r['block_before_nonzero'] is hasblock and r['block_before_matches'] is hasblock,'Block before release')
 need(r['block_dealloc_read']==(0 if mode=='hold-nocopy' else 1) and r['block_dealloc_nonzero']==(1 if is_nc else 0) and r['block_dealloc_matches']==(1 if is_nc else 0),'Block at NVIDIA dealloc')
 need(not r['witness_only_no_free'] and r['repair_attempts']==(1 if mode in ('nocopy-repair-gpu','nocopy-reject-gpu','nocopy-repair-gpu-late') else 0),'Witness attempt')
 deferred=r['gpu_deferred_applied'];need(deferred in (0,1) and r['gpu_handler_at_refusal'] in (0,1,2),'Deferred metadata')
 if repaired:need(r['repair_applied']+deferred==1 and r['repair_rejected']==deferred and r['gpu_gate_refusals']==deferred,'Deferred or direct witness')
 else:need(r['repair_applied']==deferred==r['gpu_gate_refusals']==0 and r['repair_rejected']==(1 if mode=='nocopy-reject-gpu' else 0),'Witness refusal')
 need(r['unapproved_callbacks']==0 and r['root_returned_events']==(1 if gpu and mode!='nocopy-reject-gpu' else 0),'Release authorization')
 need(r['vm_before_release']==(1 if repaired else -1) and r['vm_after_release']==(0 if repaired else -1) and r['vm_release_status']==(0 if repaired else -1),'VM release observation')
 need(r['callback_attempts']==(2 if late else (1 if repaired else 0)) and r['callback_duplicates']==(1 if late else 0) and r['synthetic_late_calls']==(1 if late else 0),'Once witness')
 need(r['pool_witness_inside'] and r['pool_witness_drained'],'Pool witness')
 d=r['drain_timeline'];need(len(d)==4 and [x['target_ms'] for x in d]==[0,250,1000,3000],'Drain timeline layout')
 previous=t[-1]
 for i,x in enumerate(d):
  need(x['elapsed_ms']>=x['target_ms'] and x['keeper_weak_nil'] is True and isinstance(x['device_weak_nil'],bool) and x['bad_args']==0,'Drain sample')
  need(x['deallocator_calls']==(1 if repaired else 0) and x['freed'] is repaired,'Drain callback')
  for key in ('entry_calls','metal_callers','cf_releases','deallocator_calls'):need(x[key]>=previous[key],'Drain counter ordering')
  if i:need(x['elapsed_ms']>=previous['elapsed_ms'],'Drain time ordering')
  previous=x
 for key,final in [('entry_calls','resource_entry_calls'),('metal_callers','metal_caller_matches'),('cf_releases','resource_release_calls'),('deallocator_calls','nocopy_deallocator_calls')]:need(r[final]>=d[-1][key],'Final counter')
 need(r['nocopy_deallocator_calls']==(1 if repaired else 0) and r['nocopy_memory_freed'] is repaired,'Final callback state')
 if mode in ('release','hold-nocopy'):need(r['nocopy_deallocator_calls']==0,'Negative callback control')

def audit(build,runs):
 need(len(runs)==len(set(runs))==6,'Six distinct hosts required');i=read(build/'inputs.json')
 for n,h in i['frozen'].items():need(sha(build/n)==h,'Frozen input '+n)
 for n in ('host.mm','observer.mm','experiment.py','race_gate.h','once_gate.h','client_callback.mm','client_state.h','client_guard.h','metal_registration.h'):need(sha(HERE/n)==i['frozen']['src/'+n],'Source changed '+n)
 need(sha(build/'application')==i['application_SHA256'] and sha(build/'libObjectObserver.dylib')==i['observer_SHA256'] and sha(build/'libClientCallback.dylib')==i['client_SHA256'],'Build artifact')
 for n in ('application','libObjectObserver.dylib','libClientCallback.dylib'):subprocess.run(['codesign','--verify','--strict',str(build/n)],capture_output=True,check=True,timeout=20)
 rows=[];pids=set();times=[];modes=[];samples=[]
 for p in runs:
  inp=read(p/'inputs.json');m=read(p/'execution/manifest.json');r=read(p/'result.json');mode=inp['mode'];rid=inp['registry_id']
  need(inp['build_inputs_SHA256']==sha(build/'inputs.json') and inp['profile']==i['profile'] and inp['observer_SHA256']==i['observer_SHA256'] and inp['client_SHA256']==i['client_SHA256'] and inp['application_SHA256']==i['application_SHA256'],'Run provenance')
  need(sha(p/'application')==sha(p/'execution/application')==i['application_SHA256'] and read(p/'execution/execution.stdout')==r and str(build/'libObjectObserver.dylib') in m['dependency_listing'] and str(build/'libClientCallback.dylib') in m['dependency_listing'],'Host artifact')
  need(sha(p/'runtime/run_sdk_host.py')==i['frozen']['runtime/run_sdk_host.py']==m['launcher_SHA256'] and sha(p/'runtime/lab_gpu_reservation.py')==i['frozen']['runtime/lab_gpu_reservation.py']==m['reservation_module_SHA256'],'Runner changed')
  manifest_check(m,mode,rid,i['application_SHA256']);check(r,mode,rid);need(r['pid']==m['pid'] and m['pid'] not in pids,'PID mismatch')
  pids.add(m['pid']);modes.append(mode);times.append((datetime.fromisoformat(m['started_at']),datetime.fromisoformat(m['completed_at'])));samples.append((r,m,mode,rid));rows.append({'mode':mode,'pid':m['pid'],'result_SHA256':sha(p/'result.json'),'manifest_SHA256':sha(p/'execution/manifest.json')})
 times.sort();need(Counter(modes)==Counter({'hold-nocopy':1,'nocopy-gpu':1,'nocopy-reject-gpu':1,'nocopy-repair-gpu':1,'nocopy-repair-gpu-late':2}) and all(a<=b for a,b in times) and all(a[1]<=b[0] for a,b in zip(times,times[1:])),'Modes or overlap')
 r,m,mode,rid=next(x for x in samples if x[2]=='nocopy-gpu');mutations=[]
 for section,key,value in [('before_a','snapshot_valid',False),('before_a','second_range_covered',0),('before_b','first_range_covered',0),('resource_a','resource_shared_matches',False),('resource_calibration','intercepted',0),('resource_calibration','entries',0),(None,'nv_dealloc_calls',0),(None,'root_branch_candidate',0),(None,'hooks_restored',False),(None,'super_control',False),(None,'first_buffer_weak_nil',False),(None,'vm_control',False),(None,'keeper_CPU_correct_after',False),(None,'nested_control',False),(None,'nested_resource_finalizer_tail',0),(None,'watched_cf_release_returns',0),(None,'root_binding_interposed',False),(None,'root_matches',0),(None,'block_ivar_pinned',False),(None,'block_before_matches',False),(None,'block_dealloc_matches',0),(None,'pool_witness_inside',False),(None,'pool_witness_drained',False)]:
  bad=copy.deepcopy(r);(bad[section] if section else bad)[key]=value
  try:check(bad,mode,rid)
  except ValueError:mutations.append(key)
  else:raise ValueError('Mutation accepted '+key)
 for label,field,value in [('keeper_not_gone','keeper_weak_nil',False),('drain_bad_args','bad_args',1),('drain_counter_regression','cf_releases',0),('drain_wrong_target','target_ms',999)]:
  bad=copy.deepcopy(r);bad['drain_timeline'][-1][field]=value
  try:check(bad,mode,rid)
  except ValueError:mutations.append(label)
  else:raise ValueError('Mutation accepted '+label)
 for field,value in [('method_status',1),('port_matches',0),('id_matches',0),('root',0),('method_end',0)]:
  bad=copy.deepcopy(r);bad['release_order'][field]=value
  try:check(bad,mode,rid)
  except ValueError:mutations.append('order_'+field)
  else:raise ValueError('Mutation accepted order_'+field)
 bad=copy.deepcopy(r);bad['gpu_words'][19]^=1
 try:check(bad,mode,rid)
 except ValueError:mutations.append('gpu_output_word')
 else:raise ValueError('Mutation accepted GPU output')
 bad=copy.deepcopy(r);bad['gpu_words'][4096+19]^=1
 try:check(bad,mode,rid)
 except ValueError:mutations.append('gpu_second_output_word')
 else:raise ValueError('Mutation accepted second GPU output')
 repaired_row=next(x for x in samples if x[2]=='nocopy-repair-gpu');rr,_,rm,rrid=repaired_row
 for field,value in [('repair_applied',1-rr['repair_applied']),('repair_rejected',1-rr['repair_rejected']),('nocopy_deallocator_calls',0),('witness_only_no_free',True),('gpu_precommit_weak_alive',False)]:
  bad=copy.deepcopy(rr);bad[field]=value
  try:check(bad,rm,rrid)
  except ValueError:mutations.append('witness_'+field)
  else:raise ValueError('Mutation accepted witness_'+field)
 for field,value in [('registration_owner_released',False),('registration_duplicate_refused',False),('registration_late_refused',False),('tracked_registered',1),('tracked_completed',1),('tracked_failures',1),('tracked_unexpected',1),('client_block_distinct',False),('client_block_retained',False),('client_library_bound',False),('client_calls',0),('client_rejected',1),('client_status',1),('vm_before_release',0),('vm_after_release',1),('vm_release_status',1),('unapproved_callbacks',1),('root_returned_events',0)]:
  bad=copy.deepcopy(rr);bad[field]=value
  try:check(bad,rm,rrid)
  except ValueError:mutations.append('vm_'+field)
  else:raise ValueError('Mutation accepted VM '+field)
 late_row=next(x for x in samples if x[2]=='nocopy-repair-gpu-late');lr,_,lm,lrid=late_row
 for field,value in [('callback_attempts',1),('callback_duplicates',0),('synthetic_late_calls',0)]:
  bad=copy.deepcopy(lr);bad[field]=value
  try:check(bad,lm,lrid)
  except ValueError:mutations.append('once_'+field)
  else:raise ValueError('Mutation accepted once_'+field)
 bad=copy.deepcopy(m);bad['GPU_reservation']['state']='unresolved'
 try:manifest_check(bad,mode,rid,i['application_SHA256'])
 except ValueError:mutations.append('reservation_not_terminal')
 else:raise ValueError('Mutation accepted reservation')
 return {'status':'PASS','hosts':6,'nonoverlapping':True,'application_SHA256':i['application_SHA256'],'observer_SHA256':i['observer_SHA256'],'client_SHA256':i['client_SHA256'],'gpu_dispatches':10,'gpu_words_verified':5*8192,'real_vm_releases':3,'real_vm_unmapped_observed':3,'synthetic_late_duplicates_suppressed':2,'native_gpu_control_hosts':1,'rejected_gpu_policy_hosts':1,'held_controls':1,'mutation_rejections':mutations,'rows':rows,'hardware_video_execution_proved':False,'limits':['Only a process-owned test allocation after two explicitly registered, completed and verified GPU commands; the independent client block and guard are tested only on this owned allocation; arbitrary callbacks and GPU clients are not supported.','A successful user-mode VM deallocation does not prove kernel object destruction or general resource safety.','Late duplicate callbacks are synthetic.','Only cooperative GPU reservation.']}
def main():
 p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--runs',type=Path,nargs=6,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'Fresh output required');r=audit(a.build.resolve(),[x.resolve() for x in a.runs]);
 with a.out.open('x') as f:json.dump(r,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps({k:v for k,v in r.items() if k!='rows'}))
if __name__=='__main__':main()
