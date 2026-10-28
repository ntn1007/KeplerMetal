#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU oracle for the separately linked public-Metal partial ICB client."""
import hashlib,importlib.util,json,sys
from pathlib import Path

def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(v,msg):
 if not v:raise ValueError(msg)
def verify(path):
 p=Path(path).resolve();i=read(p/'inputs.json');h=read(p/'execution/manifest.json');mode=i['mode'];scenario=i['scenario'];route=i['route'];lease=h['GPU_reservation'];expected=3 if mode in ('wrong-client','wrong-manifest') else 7 if mode in ('native','wrong-library') else 0
 need(mode in ('auto','native','wrong-client','wrong-manifest','wrong-library') and scenario in (0,3) and route in ('same','separate'),'Case differs')
 need(h['exit_code']==expected and not h['SIGKILL_requested'] and not h['authoritative_ps_status'] and lease['state']=='terminal' and lease['child_PID']==h['pid'] and lease['exit_code']==expected and not lease['known_signed_processes_live'],'Process or reservation differs')
 need(sha(p/'application')==i['run_executable_SHA256']==h['original_binary_sha256'] and sha(p/'execution/application')==h['signed_binary_sha256']==lease['signed_binary_sha256'],'Executable differs')
 for name,digest in i['frozen'].items():need(sha(p/name)==digest,'Frozen input differs: '+name)
 need(h['launcher_SHA256']==i['frozen']['runtime/run_host.py'] and h['reservation_module_SHA256']==i['frozen']['runtime/lab_gpu_reservation.py'],'Launcher differs')
 injected=mode!='native';need(h['injected_library_SHA256']==(i['frozen']['assets/bootstrap.dylib'] if injected else None),'Bootstrap differs')
 lib='wrong.metallib' if mode=='wrong-library' else 'partial_dual.metallib';need(h['arguments']==[str(p/'assets'/lib),str(p/'outputs'),str(scenario),route],'Arguments differ')
 trace=(p/'execution/execution.stderr').read_text();app=read(p/'execution/execution.stdout') if mode not in ('wrong-client','wrong-manifest') else None
 if app:need(app['device']=='NVIDIA GeForce GTX 880M' and app['pid']==h['pid'] and app['scenario']==scenario and app['route']==route and app['registry_id']==i['registry_id'],'Device differs')
 if mode=='auto':
  need(app['status']=='PASS' and app['command_status']==4 and app['copy_status']==4 and app['geometry_refused'] and app['uncommitted_order_refused']==(route=='separate') and all(x in trace for x in ('KM_BOOT enabled','KM_BOOT queue matched','KM_BOOT library snapshot approved','KM_BOOT compute pipeline matched partial_builtin_barrier','KM_BOOT compute pipeline matched partial_buffer_stencil','KM_BOOT labelled blit adapted','KM_BOOT GPU copy encoded')),'Adaptation differs')
  need(app['device_class'].startswith('KPICBDevice_') and app['queue_class'].startswith('KPAutomaticQueue_') and app['command_buffer_class'].startswith('KPAutomaticCommandBuffer_') and app['compute_encoder_class'].startswith('KPICBEncoder_') and app['blit_encoder_class'].startswith('KMPinnedBlit_'),'Automatic classes differ')
  spec=importlib.util.spec_from_file_location('dual_oracle',p/'src/verify_partial_gpu_dual_copy.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);n=75 if scenario==3 else 96
  for phase,active in [('before',False),('after',True)]:
   values=mod.expected(n,'same',active,scenario)
   for k in ('b','geo','c','x','geox','y','count1','count2','count3','count4'):need((p/'outputs'/f'{phase}.{k}.bin').read_bytes()==values[k],'CPU oracle differs: '+phase+' '+k)
  events=read(p/'events.json');es=[x for x in events if x['operation']=='execute_bounded_partial_range'];need(len(es)==1,'Execution event differs');e=es[0];proof=e['evidence'];regions=5 if scenario==3 else 3
  need(e['location']==0 and e['length']==2 and [x['partial'] for x in e['slots']]==[True,False] and [x['launches'] for x in e['slots']]==([4,1] if scenario==3 else [2,1]) and all(x['GPU_copied'] for x in e['slots']) and proof['resident_launches']==regions and e['serial_wait_after_each_launch'] and not e['native_ICB'],'Partial range differs')
  copies=[x for x in events if x['operation']=='GPU_partial_QMD_copy'];need(len(copies)==1,'Copy event differs');copy=copies[0];pairs=copy['descriptor_pairs'];need(copy['length']==2 and copy['regions']==copy['encoded_GPU_blits']==regions and copy['bytes']==256*regions and copy['whole_range_preflight'] and not copy['native_ICB'] and copy['retained_owners']==regions*2 and proof['descriptor_GPU_addresses']==[x['destination'] for x in pairs],'Copy descriptors differ')
  orders=e['predecessor_order'];need(len(orders)==2 and all(x['kind'] in (('committed_same_queue_predecessor','completed_predecessor') if route=='separate' else ('same_recording_CB',)) for x in orders),'Copy ordering differs')
  profiles=proof['owner_original_profiles'];by_address={x['descriptor_GPU_address']:x for x in profiles};need(len(by_address)==len(profiles)==regions*2,'Owner profile identity differs');names=['partial_builtin_barrier']*(regions-1)+['partial_buffer_stencil']
  for pair,name in zip(pairs,names):
   for address in (pair['source'],pair['destination']):
    x=by_address.get(address);need(x and x['original_record_function']==name and x['native_register_count']==(22 if name=='partial_builtin_barrier' else 11),'Profile evidence differs')
  need(any(x['operation']=='automatic_compute_factories_enabled' for x in events) and any(x['operation']=='automatic_compute_encoder' for x in events),'Factory events missing')
 elif mode=='native':need(not trace and app['status']=='FAIL' and 'newIndirectCommandBufferWithDescriptor:maxCount:options:' in app['failure'] and 'unrecognized selector' in app['failure'] and not list((p/'outputs').iterdir()),'Native control differs')
 elif mode=='wrong-library':need('KM_BOOT library unapproved' in trace and app['status']=='FAIL' and 'Pipeline is not owned' in app['failure'] and not list((p/'outputs').iterdir()),'Wrong-library control differs')
 else:need('KM_BOOT identity refused' in trace and 'KM_BOOT enabled' not in trace and not (p/'events.json').exists() and not (p/'execution/execution.stdout').read_text(),'Identity refusal differs')
 return {'status':'PASS','mode':mode,'scenario':scenario,'route':route,'committed_copy_blits':(5 if scenario==3 else 3) if mode=='auto' else 0,'GPU_dispatches':2 if mode=='auto' else 0,'GPU_invocations':2*(75 if scenario==3 else 96) if mode=='auto' else 0,'correct_uint32_words':12*(75 if scenario==3 else 96) if mode=='auto' else 0,'public_client_only':True,'general_application_compatibility':False,'system_modified':False}
if __name__=='__main__':print(json.dumps(verify(sys.argv[1]),sort_keys=True))
