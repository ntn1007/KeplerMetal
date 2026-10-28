#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify one partial-grid GPU copy, ordering and output against a CPU oracle."""
import hashlib,json,struct,sys
from pathlib import Path
LIB='0985a3057cd487352d801abcd180bf05a681b8dc7357ee5400db044098c32c4c'
MANIFEST='c7dcdc81adba7f7ba6cf8175ecc179a086a9bd150b44d71ca1a39ad18846ef9a'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def need(v,why):
 if not v:raise ValueError(why)
def expected(n,mode,active,scenario):
 grid=(5,5,3) if scenario==3 else (96,1,1);local=(4,4,3) if scenario==3 else (65,1,1);groups=tuple((g+l-1)//l for g,l in zip(grid,local))
 a=[(i*17+1,i*3+7,i^0x12345,i*13+11) for i in range(n)];blank=[(0xa5a5a5a5,)*4 for _ in range(n)]
 def pack(v):return v[0]|v[1]<<10|v[2]<<20
 coords=[];geometry=[]
 for z in range(grid[2]):
  for y in range(grid[1]):
   for x in range(grid[0]):
    gid=(x,y,z);group=tuple(v//l for v,l in zip(gid,local));lane=tuple(v%l for v,l in zip(gid,local));actual=tuple(min(l,g-k*l) for g,l,k in zip(grid,local,group));idx=lane[0]+actual[0]*(lane[1]+actual[1]*lane[2]);size=actual[0]*actual[1]*actual[2]
    coords.append((pack(gid),pack(lane),pack(group),pack(groups)));geometry.append((pack(actual),pack(local),pack(grid),((idx+32)%size)^0x3141))
 def transform(rows,seed):return [(x[0]^rows[(i+1)%n][1]^seed,(x[1]+rows[(i+1)%n][2])&0xffffffff,x[2]^rows[(i+1)%n][3],(x[3]+rows[(i+1)%n][0]+seed)&0xffffffff) for i,x in enumerate(rows)]
 copied=active and mode in ('same','separate');native=active and mode=='native'
 b=coords if copied else blank;geo=geometry if copied else blank;c=transform(coords,0x1234) if copied else blank
 x=coords if native else blank;geox=geometry if native else blank;y=transform(coords,0x1234) if native else blank
 def array(rows):return b'\xa5'*64+b''.join(struct.pack('<4I',*v) for v in rows)+b'\xa5'*64
 def counter(v):return b'\xa5'*64+struct.pack('<I',v)+b'\xa5'*64
 return {'a':array(a),'b':array(b),'c':array(c),'geo':array(geo),'x':array(x),'y':array(y),'geox':array(geox),'count1':counter(n if copied else 0),'count2':counter(n if copied else 0),'count3':counter(n if native else 0),'count4':counter(n if native else 0)}
def verify(root):
 root=Path(root).resolve();i=read(root/'inputs.json');r=read(root/'results.json');m=read(root/'execution/manifest.json');lease=m['GPU_reservation'];mode=i['mode'];scenario=i['case_index'];n=75 if scenario==3 else 96;regions=5 if scenario==3 else 3
 need(mode in ('prepare','native','same','separate') and scenario in (0,3) and r==read(root/'execution/execution.stdout') and r['status']=='PASS' and r['mode']==mode and r['scenario']==scenario and r['scope_restored'] and not r['system_modified'],'Result differs')
 need(r['device']=='NVIDIA GeForce GTX 880M' and r['registry_id']==i['registry_id'] and m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and lease['state']=='terminal' and lease['child_PID']==m['pid']==r['pid'] and not lease['known_signed_processes_live'],'Device or process differs')
 need(m['arguments']==[str(root/'assets/partial_dual.metallib'),str(root/'assets/partial_dual.json'),str(root/'outputs'),mode,str(i['registry_id']),str(scenario)],'Arguments differ')
 need(sha(root/'assets/partial_dual.metallib')==i['library_SHA256']==LIB and sha(root/'assets/partial_dual.json')==i['manifest_SHA256']==MANIFEST,'Library differs')
 for name,h in i['frozen'].items():need(sha(root/name)==h,'Frozen input differs: '+name)
 need(sha(root/'runtime_archive.a')==i['runtime_archive_SHA256'] and sha(root/'application')==i['executable_SHA256']==m['original_binary_sha256'] and sha(root/'execution/application')==m['signed_binary_sha256']==lease['signed_binary_sha256'],'Artifact differs')
 need(m['launcher_SHA256']==i['frozen']['runtime/run_sdk_host.py'] and m['reservation_module_SHA256']==i['frozen']['runtime/lab_gpu_reservation.py'],'Launcher differs')
 need(r['disabled_refused'] and r['unprepared_refused'] and r['too_many_refused_before_materialization'] and r['geometry_mismatch_refused'] and r['uniform_unprepared_refused'] and r['uniform_mismatch_refused'] and r['pipeline_mismatch_refused'] and r['over_range_refused'] and r['committed']==(mode!='prepare') and r['command_status']==(0 if mode=='prepare' else 4),'Controls or command status differ')
 event=r['execution_event'];need(event['operation']=='execute_bounded_partial_range' and event['location']==0 and event['length']==2 and [x['index'] for x in event['slots']]==[0,1] and [x['launches'] for x in event['slots']]==([4,1] if scenario==3 else [2,1]) and all(x['GPU_copied']==(mode!='native') for x in event['slots']) and not event['native_ICB'] and event['serial_wait_after_each_launch'],'Execution event differs')
 proof=event['evidence'];need(proof['resident_launches']==regions and proof['command_bytes']==24*regions and not proof['native_preparation_GPU_dispatches'] and not proof['CPU_constant_uploads_in_launch'],'Resident stream differs')
 if mode=='native':need(not r['copy_event'] and not r['overwrite_refused'] and not r['ordering_refused'],'Native control differs')
 else:
  c=r['copy_event'];pairs=c['descriptor_pairs'];need(c['operation']=='GPU_partial_QMD_copy' and c['regions']==c['encoded_GPU_blits']==regions and c['bytes']==regions*256 and c['length']==2 and [x['regions'] for x in c['slots']]==([4,1] if scenario==3 else [2,1]) and c['retained_owners']==regions*2 and c['whole_range_preflight'] and not c['native_ICB'] and len(pairs)==regions and r['overwrite_refused'] and r['uniform_overwrite_refused'] and r['uniform_setter_refused'] and r['ordering_refused']==(mode=='separate'),'Copy event differs')
  addresses=[x[k] for x in pairs for k in ('source','destination')];need(len(set(addresses))==regions*2 and all(addresses),'Descriptor identity differs')
  need(proof['owners']==regions*2 and proof['descriptor_GPU_addresses']==[x['destination'] for x in pairs],'Executed descriptors differ')
  orders=event['predecessor_order'];need(len(orders)==2 and all(x['kind'] in (('committed_same_queue_predecessor','completed_predecessor') if mode=='separate' else ('same_recording_CB',)) for x in orders),'Predecessor ordering differs')
 for phase,active in [('before',False)]+([('after',True)] if mode!='prepare' else []):
  for key,value in expected(n,mode,active,scenario).items():need((root/'outputs'/f'{phase}.{key}.bin').read_bytes()==value,'CPU oracle differs: '+phase+' '+key)
 return {'status':'PASS','mode':mode,'scenario':scenario,'regions':regions,'GPU_user_dispatches':0 if mode=='prepare' else 2,'GPU_invocations':0 if mode=='prepare' else n*2,'correct_uint32_words':0 if mode=='prepare' else n*12,'copy_blits':0 if mode=='native' else regions,'uncommitted_order_refused':r['ordering_refused'],'geometry_mismatch_refused':True,'over_eight_refused_before_materialization':True,'whole_range_over_eight_refused':True,'uniform_controls_pass':True,'pipeline_mismatch_refused':True,'second_slot_uniform':True,'native_apple_ICB':False}
if __name__=='__main__':print(json.dumps(verify(sys.argv[1]),sort_keys=True))
