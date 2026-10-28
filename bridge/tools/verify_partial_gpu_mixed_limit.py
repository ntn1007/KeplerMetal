#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify one partial-grid GPU copy, ordering and output against a CPU oracle."""
import hashlib,json,struct,sys
from pathlib import Path
LIB='1d7f936b2f110c99f889518c5ab654447fbdcd0b2215a4a8a14748684a907658'
MANIFEST='4edd2edd2bb70975dcfdac23d98f355f61a30edcd5bdd61fdd695e5a9144b428'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def need(v,why):
 if not v:raise ValueError(why)
def expected(n,mode,active):
 a=[(i*17+1,i*3+7,i^0x12345,i*13+11) for i in range(n)];blank=[(0xa5a5a5a5,)*4 for _ in range(n)]
 def transform(rows,seed):
  return [(x[0]^rows[(i+1)%n][1]^seed,(x[1]+rows[(i+1)%n][2])&0xffffffff,x[2]^rows[(i+1)%n][3],(x[3]+rows[(i+1)%n][0]+seed)&0xffffffff) for i,x in enumerate(rows)]
 b=transform(a,0x3141) if active and mode in ('same','separate') else blank;c=transform(b,0x1234) if active and mode in ('same','separate') else blank
 x=transform(a,0x3141) if active and mode=='native' else blank;y=transform(x,0x1234) if active and mode=='native' else blank
 def array(rows):return b'\xa5'*64+b''.join(struct.pack('<4I',*v) for v in rows)+b'\xa5'*64
 def counter(v):return b'\xa5'*64+struct.pack('<I',v)+b'\xa5'*64
 return {'a':array(a),'b':array(b),'c':array(c),'x':array(x),'y':array(y),'count1':counter(n if active and mode in ('same','separate') else 0),'count2':counter(n if active and mode in ('same','separate') else 0),'count3':counter(n if active and mode=='native' else 0),'count4':counter(n if active and mode=='native' else 0)}
def verify(root):
 root=Path(root).resolve();i=read(root/'inputs.json');r=read(root/'results.json');m=read(root/'execution/manifest.json');lease=m['GPU_reservation'];mode=i['mode'];scenario=i['case_index'];n=75 if scenario==3 else 96;regions=5 if scenario==3 else 3
 need(mode in ('prepare','native','same','separate') and scenario in (0,3) and r==read(root/'execution/execution.stdout') and r['status']=='PASS' and r['mode']==mode and r['scenario']==scenario and r['scope_restored'] and not r['system_modified'],'Result differs')
 need(r['device']=='NVIDIA GeForce GTX 880M' and r['registry_id']==i['registry_id'] and m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and lease['state']=='terminal' and lease['child_PID']==m['pid']==r['pid'] and not lease['known_signed_processes_live'],'Device or process differs')
 need(m['arguments']==[str(root/'assets/partial_buffer_stencil.metallib'),str(root/'assets/partial_buffer_stencil.json'),str(root/'outputs'),mode,str(i['registry_id']),str(scenario)],'Arguments differ')
 need(sha(root/'assets/partial_buffer_stencil.metallib')==i['library_SHA256']==LIB and sha(root/'assets/partial_buffer_stencil.json')==i['manifest_SHA256']==MANIFEST,'Library differs')
 for name,h in i['frozen'].items():need(sha(root/name)==h,'Frozen input differs: '+name)
 need(sha(root/'runtime_archive.a')==i['runtime_archive_SHA256'] and sha(root/'application')==i['executable_SHA256']==m['original_binary_sha256'] and sha(root/'execution/application')==m['signed_binary_sha256']==lease['signed_binary_sha256'],'Artifact differs')
 need(m['launcher_SHA256']==i['frozen']['runtime/run_sdk_host.py'] and m['reservation_module_SHA256']==i['frozen']['runtime/lab_gpu_reservation.py'],'Launcher differs')
 need(r['disabled_refused'] and r['unprepared_refused'] and r['too_many_refused_before_materialization'] and r['geometry_mismatch_refused'] and r['uniform_unprepared_refused'] and r['uniform_mismatch_refused'] and r['mixed_limit_refused'] and r['over_range_refused'] and r['committed']==(mode!='prepare') and r['command_status']==(0 if mode=='prepare' else 4),'Controls or command status differ')
 event=r['execution_event'];need(event['operation']=='execute_bounded_partial_range' and event['location']==0 and event['length']==2 and [x['index'] for x in event['slots']]==[0,1] and [x['launches'] for x in event['slots']]==([4,1] if scenario==3 else [2,1]) and all(x['GPU_copied']==(mode!='native') for x in event['slots']) and not event['native_ICB'] and event['serial_wait_after_each_launch'],'Execution event differs')
 proof=event['evidence'];need(proof['resident_launches']==regions and proof['command_bytes']==24*regions and not proof['native_preparation_GPU_dispatches'] and not proof['CPU_constant_uploads_in_launch'],'Resident stream differs')
 if mode=='native':need(not r['copy_event'] and not r['overwrite_refused'] and not r['ordering_refused'],'Native control differs')
 else:
  c=r['copy_event'];pairs=c['descriptor_pairs'];need(c['operation']=='GPU_partial_QMD_copy' and c['regions']==c['encoded_GPU_blits']==regions and c['bytes']==regions*256 and c['length']==2 and [x['regions'] for x in c['slots']]==([4,1] if scenario==3 else [2,1]) and c['retained_owners']==regions*2 and c['whole_range_preflight'] and not c['native_ICB'] and len(pairs)==regions and r['overwrite_refused'] and r['uniform_overwrite_refused'] and r['uniform_setter_refused'] and r['ordering_refused']==(mode=='separate'),'Copy event differs')
  addresses=[x[k] for x in pairs for k in ('source','destination')];need(len(set(addresses))==regions*2 and all(addresses),'Descriptor identity differs')
  need(proof['owners']==regions*2 and proof['descriptor_GPU_addresses']==[x['destination'] for x in pairs],'Executed descriptors differ')
  orders=event['predecessor_order'];need(len(orders)==2 and all(x['kind'] in (('committed_same_queue_predecessor','completed_predecessor') if mode=='separate' else ('same_recording_CB',)) for x in orders),'Predecessor ordering differs')
 for phase,active in [('before',False)]+([('after',True)] if mode!='prepare' else []):
  for key,value in expected(n,mode,active).items():need((root/'outputs'/f'{phase}.{key}.bin').read_bytes()==value,'CPU oracle differs: '+phase+' '+key)
 return {'status':'PASS','mode':mode,'scenario':scenario,'regions':regions,'GPU_user_dispatches':0 if mode=='prepare' else 2,'GPU_invocations':0 if mode=='prepare' else n*2,'correct_uint32_words':0 if mode=='prepare' else n*8,'copy_blits':0 if mode=='native' else regions,'uncommitted_order_refused':r['ordering_refused'],'geometry_mismatch_refused':True,'over_eight_refused_before_materialization':True,'whole_range_over_eight_refused':True,'uniform_controls_pass':True,'mixed_limit_refused':True,'second_slot_uniform':True,'native_apple_ICB':False}
if __name__=='__main__':print(json.dumps(verify(sys.argv[1]),sort_keys=True))
