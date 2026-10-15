#!/usr/bin/env python3
"""Offline proof audit for ordinary queue/buffer/compute factory integration."""
from pathlib import Path
import argparse,hashlib,json
from verify_command_ir_dataflow import verify as numeric
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def terminal(root):
 m=load(root/'execution/manifest.json');assert m['exit_code']==0 and not m['SIGKILL_requested']and not m['authoritative_ps_status']and m['GPU_reservation']['state']=='terminal'
 inp=load(root/'inputs.json');assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256']
 for n,h in inp['source_hashes'].items():assert sha(root/n)==h
 return inp

def verify():
 progress=ROOT/'results/ordinary-queue-progress-20261015';lib=ROOT/'results/ordinary-queue-runtime-library-build-20261015-03';lm=load(lib/'manifest.json');pin=sha(lib/'libKeplerMetal.a');assert pin==lm['static_library_SHA256']
 for n,h in lm['source_SHA256'].items():assert sha(lib/n)==sha(ROOT/n)==h
 native=ROOT/'results/native-queue-factory-probe-20261015';terminal(native);nd=load(native/'results.json');assert len(nd['runs'])==20 and all(x['created']and not x['committed']and not x['exception']and x['retained_references']==(x['buffer_factory']in[0,2])for x in nd['runs'])and nd['user_GPU_command_buffers']==0
 cpu=ROOT/'results/ordinary-queue-contract-probe-20261015';assert terminal(cpu)['static_library_SHA256']==pin;cd=load(cpu/'results.json');assert len(cd['runs'])==93 and all(x['PASS']for x in cd['runs'])and cd['scope_released_with_reflection_alive']and not cd['command_buffers_submitted']
 automatic=[x for x in cd['runs']if x['kind']=='automatic_public_factory'];assert len(automatic)==20 and all(x['no_manual_adaptation']and x['refused_before_native_cursor_write']and not x['committed']for x in automatic)
 assert load(ROOT/'results/ordinary-queue-lifecycle-qualification-20261015/status.json')['status']=='PASS'
 lifecases=0;special=[]
 for h in load(ROOT/'results/ordinary-queue-lifecycle-qualification-20261015/history.json'):
  root=Path(h['result']);assert terminal(root)['static_library_SHA256']==pin;d=load(root/'results.json');assert len(d['runs'])==42 and all(x['PASS']for x in d['runs'])and d['scope_released_with_reflection_alive'];lifecases+=len(d['runs']);special.extend(x for x in d['runs']if x['kind'].startswith('automatic_'))
  if h['mode']=='automatic_blocking':
   row=next(x for x in d['runs']if x['kind']=='automatic_restore_during_native_pool_wait');assert d['command_buffers_submitted']and row['worker_waiting_observed']and not row['early_completion']and row['empty_command_buffer_status']==4 and row['user_kernel_dispatches']==0
  else:assert not d['command_buffers_submitted']
 cases=[]
 for folder,kind in [('ordinary-queue-pipeline-qualification-20261015','pipeline'),('ordinary-queue-factory-qualification-20261015','public_factories')]:
  suite=ROOT/'results'/folder;assert load(suite/'status.json')['status']=='PASS'
  for h in load(suite/'history.json'):
   assert h['exit_code']==0
   if h['phase']!='CPU':continue
   root=Path(h['result']);v=numeric(root);d=load(root/'results.json');inp=terminal(root);assert inp['static_library_SHA256']==pin and inp['automatic_encoders']and d['automatic_encoders']and d['manual_compute_adaptation_calls']==0
   assert 'adaptComputeEncoder:'not in(root/'command_ir_dataflow_client.mm').read_text();assert sha(root/'QueueFactoryReception.inc')==sha(ROOT/'tools/QueueFactoryReception.inc')
   q=h['queue_factory']if kind=='public_factories'else 0;e=h['encoder_factory']if kind=='public_factories'else 0;p=5 if kind=='public_factories'else h['factory_kind'];assert d['queue_factory_kind']==q and d['encoder_factory_kind']==e and d['factory_kind']==p
   assert d['factory_evidence']['requested_max_threads']==(32 if p in[2,5]else 0)and d['factory_evidence']['max_threads']==(32 if p in[2,5]else 1024)
   events=d['function_events'];assert any(x['operation']=='automatic_compute_factories_enabled'for x in events);assert any(x['operation']=='automatic_compute_factories_restored'and x['queue_class_restored']for x in events);assert any(x['operation']=='automatic_compute_encoder'for x in events);assert all(x['class_layout_preserved']for x in events if x['operation']=='automatic_command_buffer')
   cases.append({'suite':kind,'pipeline_factory':p,'queue_factory':q,'encoder_factory':e,'mode':h['mode'],**{k:v[k]for k in ['trials','exact_uint32_results','consumer_invocations','guard_bytes']}})
 reference=ROOT/'results/ordinary-queue-M1-return-20261015/Reference';client=ROOT/'results/ordinary-queue-reception-client-build-20261015';returned=load(reference/'REFERENCE_RETURN.json')
 for row in returned['files']:assert sha(reference/row['path'])==row['SHA256']
 for name in ['command_ir_dataflow_client.mm','PipelineFactoryReception.inc','QueueFactoryReception.inc']:assert sha(reference/name)==sha(client/name)
 matches=[]
 for mode in ['no_producer','barrier','no_consumer']:
  assert numeric(reference/'results'/mode)['status']=='PASS';d=load(reference/'results'/mode/'results.json');assert d['queue_factory_kind']==1 and d['encoder_factory_kind']==4 and d['factory_kind']==5
  # no-producer/no-consumer controls use the default factory route; compare only
  # semantic buffers, never hardware-specific argument tables or QMD records.
  target=ROOT/'results'/('ordinary-queue-factories-20261015-q1-e4-'+mode)if mode=='barrier'else ROOT/'results'/('ordinary-queue-final-20261015-k5-'+mode)
  for trial in d['runs']:
   for name in ['input','dummySrc','stage0','stage1','stage2','counter','dummyCounter',*[f'dummy{i}'for i in range(6)]]:
    file=trial['files'][name];assert sha(reference/'results'/mode/'outputs'/file)==sha(target/'outputs'/file);matches.append({'mode':mode,'file':file,'SHA256':sha(target/'outputs'/file)})
 assert len(matches)==156
 baseline=load(ROOT/'results/pipeline-contract-runtime-progress-20261015/final-verification.json');assert len(baseline['system_files'])==83 and all(sha(r['path'])==r['baseline_SHA256']for r in baseline['system_files']);assert sha('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist')==baseline['OCLP_SHA256']
 return {'status':'PASS','static_library_SHA256':pin,'source_manifest_SHA256':sha(lib/'manifest.json'),'GPU_cohorts':len(cases),'GPU_trials':sum(x['trials']for x in cases),'exact_uint32_results':sum(x['exact_uint32_results']for x in cases),'consumer_invocations':sum(x['consumer_invocations']for x in cases),'guard_bytes':sum(x['guard_bytes']for x in cases),'cases':cases,'CPU_native_factory_observations':20,'CPU_contract_cases':93,'lifecycle_and_factory_cases':lifecases,'special_lifecycle_controls':special,'empty_command_buffers_in_pool_control':1,'user_kernel_dispatches_in_pool_control':0,'manual_adaptation_calls_in_reception_client':0,'public_GPU_factory_combinations':10,'public_CPU_factory_combinations':20,'M1_trials':12,'M1_identical_common_files':156,'M1_same_client_SHA256':sha(client/'command_ir_dataflow_client.mm'),'M1_semantic_matches':matches,'system_files_unchanged':83,'OCLP_unchanged':True,'integration_level':2,'scope':'Explicitly registered producer functions and the one scope-owned queue; other queues remain native','preexisting_command_buffers_automatically_adapted':False,'arbitrary_libraries_supported':False,'unretained_IR_GPU_dataflow':'NOT RUN; existing retained-reference preconditions preserved','performance_benchmark':False,'full_objective_complete':False}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=verify();out=a.out.resolve();out.relative_to(ROOT/'results')
 with out.open('x')as f:json.dump(d,f,indent=2);f.write('\n')
 print(json.dumps({k:v for k,v in d.items()if k not in['cases','M1_semantic_matches']},indent=2))
