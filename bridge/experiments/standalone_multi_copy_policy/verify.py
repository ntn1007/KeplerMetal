#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent CPU and policy oracle for two public-Metal test clients."""
import hashlib,importlib.util,json,sys
from pathlib import Path

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(v,msg):
 if not v:raise ValueError(msg)
def verify(path):
 p=Path(path).resolve();i=read(p/'inputs.json');h=read(p/'execution/manifest.json');mode=i['mode'];tag=i['tag'];scenario=i['scenario'];route=i['route'];lease=h['GPU_reservation'];denied=('denied-b','wrong-policy','malformed-policy','wrong-client','wrong-manifest');expected=3 if mode in denied else 7 if mode in ('native-a','native-b','wrong-library') else 0
 need(mode in ('native-a','native-b','optin-a','optin-b',*denied,'wrong-library') and tag in ('a','b') and scenario in (0,3) and route in ('same','separate'),'Case differs')
 need(h['exit_code']==expected and not h['SIGKILL_requested'] and not h['authoritative_ps_status'] and lease['state']=='terminal' and lease['child_PID']==h['pid'] and lease['exit_code']==expected and not lease['known_signed_processes_live'],'Process or reservation differs')
 need(sha(p/'application')==i['run_executable_SHA256']==h['original_binary_sha256'] and sha(p/'execution/application')==h['signed_binary_sha256']==lease['signed_binary_sha256'],'Executable differs')
 for name,digest in i['frozen'].items():
  if mode=='wrong-policy' and name=='assets/'+i['policy_name']:continue
  need(sha(p/name)==digest,'Frozen input differs: '+name)
 need(h['launcher_SHA256']==i['frozen']['runtime/run_host.py'] and h['reservation_module_SHA256']==i['frozen']['runtime/lab_gpu_reservation.py'],'Launcher differs')
 injected=not mode.startswith('native-');need(h['injected_library_SHA256']==(i['frozen']['assets/bootstrap.dylib'] if injected else None),'Bootstrap differs')
 policy=p/'assets'/i['policy_name'];policyHash=sha(policy);need((policyHash!=i['policy_expected_SHA256'])==(mode=='wrong-policy'),'Policy hash control differs')
 if mode=='malformed-policy':
  members=read(policy)['allowed_clients'];need(len(members)==2 and members[0]==members[1],'Malformed policy differs')
 if mode=='denied-b':need(i['executable_B_SHA256'] not in read(policy)['allowed_clients'],'Client B unexpectedly allowed')
 lib='wrong.metallib' if mode=='wrong-library' else 'partial_dual.metallib';need(h['arguments']==[str(p/'assets'/lib),str(p/'outputs'),str(scenario),route],'Arguments differ')
 trace=(p/'execution/execution.stderr').read_text();app=read(p/'execution/execution.stdout') if mode not in denied else None
 if app:need(app['device']=='NVIDIA GeForce GTX 880M' and app['pid']==h['pid'] and app['scenario']==scenario and app['route']==route and app['registry_id']==i['registry_id'],'Device differs')
 if mode in ('optin-a','optin-b'):
  expectedClient=i['executable_A_SHA256'] if tag=='a' else i['executable_B_SHA256'];need(i['run_executable_SHA256']==h['signed_binary_sha256']==expectedClient and expectedClient in read(policy)['allowed_clients'] and 'KM_BOOT policy accepted '+expectedClient+' '+i['policy_expected_SHA256'] in trace,'Selected policy/client differs')
  need(app['status']=='PASS' and app['command_status']==4 and app['copy_status']==4 and app['geometry_refused'] and app['uncommitted_order_refused']==(route=='separate') and all(x in trace for x in ('KM_BOOT enabled','KM_BOOT queue matched','KM_BOOT library snapshot approved','KM_BOOT compute pipeline matched partial_builtin_barrier','KM_BOOT compute pipeline matched partial_buffer_stencil','KM_BOOT object GPU copy encoded')),'Adaptation differs')
  need(app['device_class'].startswith('KPICBDevice_') and app['queue_class'].startswith('KPAutomaticQueue_') and app['command_buffer_class'].startswith('KPAutomaticCommandBuffer_') and app['compute_encoder_class'].startswith('KPICBEncoder_') and app['blit_encoder_class'].startswith('KMAutoBlit_'),'Automatic classes differ')
  if tag=='a':need(app['invalid_range_refused'] and app['overlap_refused'] and app['unretained_refused'] and app['over_limit_refused'] and app['independent_copies_encoded'] and app['dependent_copy_refused'] and app['dependent_buffer_discarded_uncommitted'] and trace.count('KM_BOOT additional GPU copy encoded')==1 and trace.count('KM_BOOT additional copy refused before preflight')==1 and app['ordinary_blit_class'].startswith('KMAutoBlit_') and app['ordinary_blit_after_end_class'].startswith('NVMTL') and app['copy_blit_after_end_class'].startswith('NVMTL') and trace.count('KM_BOOT preflight refused materializations 0 0')>=4,'Client A controls differ')
  else:need('KM_BOOT preflight refused materializations 0 0' in trace,'Client B geometry preflight differs')
  spec=importlib.util.spec_from_file_location('dual_oracle',p/'src/verify_partial_gpu_dual_copy.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);n=75 if scenario==3 else 96
  for phase,active in [('before',False),('after',True)]:
   values=mod.expected(n,'same',active,scenario)
   for k in ('b','geo','c','x','geox','y','count1','count2','count3','count4'):need((p/'outputs'/f'{phase}.{k}.bin').read_bytes()==values[k],'CPU oracle differs: '+phase+' '+k)
   if tag=='a':
    for k,original in {'b2':'b','geo2':'geo','c2':'c','x2':'x','geox2':'geox','y2':'y','count5':'count1','count6':'count2','count7':'count3','count8':'count4'}.items():need((p/'outputs'/f'{phase}.{k}.bin').read_bytes()==values[original],'Second CPU oracle differs: '+phase+' '+k)
  events=read(p/'events.json');es=[x for x in events if x['operation']=='execute_bounded_partial_range'];prepared=[x for x in events if x['operation']=='prepare_automatic_partial_GPU_copy'];copies=[x for x in events if x['operation']=='GPU_partial_QMD_copy'];amount=2 if tag=='a' else 1;need(len(es)==amount and len(prepared)==len(copies)==amount+(1 if tag=='a' else 0),'Independent copy/execution event count differs');prepared=prepared[-amount:];copies=copies[-amount:];regions=5 if scenario==3 else 3;source=1 if tag=='a' and scenario==3 else 0;target=2 if tag=='a' and scenario==3 else 0;all_addresses=[]
  for e,prep,c in zip(es,prepared,copies):
   proof=e['evidence'];pairs=c['descriptor_pairs'];need(e['location']==target and e['length']==2 and [x['partial'] for x in e['slots']]==[True,False] and [x['launches'] for x in e['slots']]==([4,1] if scenario==3 else [2,1]) and all(x['GPU_copied'] for x in e['slots']) and proof['resident_launches']==regions and e['serial_wait_after_each_launch'] and not e['native_ICB'],'Partial range differs')
   need(prep['source_location']==source and prep['destination_index']==target and prep['whole_range_preflight_before_initialization'] and not prep['user_kernel_dispatches'],'Preflight evidence differs');need(c['source_location']==source and c['destination_index']==target and c['length']==2 and c['regions']==c['encoded_GPU_blits']==regions and c['bytes']==regions*256 and c['whole_range_preflight'] and not c['native_ICB'] and c['retained_owners']==regions*2 and proof['descriptor_GPU_addresses']==[x['destination'] for x in pairs],'Copy descriptors differ')
   orders=e['predecessor_order'];need(len(orders)==2 and all(x['kind'] in (('committed_same_queue_predecessor','completed_predecessor') if route=='separate' else ('same_recording_CB',)) for x in orders),'Copy ordering differs')
   profiles=proof['owner_original_profiles'];by_address={x['descriptor_GPU_address']:x for x in profiles};need(len(by_address)==len(profiles)==regions*2,'Owner profile identity differs');names=['partial_builtin_barrier']*(regions-1)+['partial_buffer_stencil']
   for pair,name in zip(pairs,names):
    for address in (pair['source'],pair['destination']):
     all_addresses.append(address);x=by_address.get(address);need(x and x['original_record_function']==name and x['native_register_count']==(22 if name=='partial_builtin_barrier' else 11),'Native profile differs')
  need(len(set(all_addresses))==len(all_addresses),'Copy owners overlap')
 elif mode.startswith('native-'):need(not trace and app['status']=='FAIL' and 'newIndirectCommandBufferWithDescriptor:maxCount:options:' in app['failure'] and 'unrecognized selector' in app['failure'] and not list((p/'outputs').iterdir()),'Native control differs')
 elif mode=='wrong-library':need('KM_BOOT library unapproved' in trace and app['status']=='FAIL' and 'Pipeline is not owned' in app['failure'] and not list((p/'outputs').iterdir()),'Wrong library control differs')
 else:
  reason='KM_BOOT policy refused' if mode in ('wrong-policy','malformed-policy') else 'KM_BOOT identity refused';need(reason in trace and 'KM_BOOT enabled' not in trace and not (p/'events.json').exists() and not (p/'execution/execution.stdout').read_text(),'Expected refusal differs')
 return {'status':'PASS','mode':mode,'tag':tag,'scenario':scenario,'route':route,'committed_copy_blits':(5 if scenario==3 else 3)*(2 if tag=='a' else 1) if mode.startswith('optin-') else 0,'GPU_dispatches':(4 if tag=='a' else 2) if mode.startswith('optin-') else 0,'GPU_invocations':(4 if tag=='a' else 2)*(75 if scenario==3 else 96) if mode.startswith('optin-') else 0,'correct_uint32_words':(24 if tag=='a' else 12)*(75 if scenario==3 else 96) if mode.startswith('optin-') else 0,'public_client_only':True,'general_application_compatibility':False,'system_modified':False}
if __name__=='__main__':print(json.dumps(verify(sys.argv[1]),sort_keys=True))
