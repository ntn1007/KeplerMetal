#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU oracle for two serial partial/uniform producer-consumer ICB slots."""
import hashlib,json,struct,sys
from pathlib import Path
LIB='1d7f936b2f110c99f889518c5ab654447fbdcd0b2215a4a8a14748684a907658'
MANIFEST='4edd2edd2bb70975dcfdac23d98f355f61a30edcd5bdd61fdd695e5a9144b428'
N=96

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())
def require(ok,message):
 if not ok:raise ValueError(message)
def transform(source,seed):
 out=[]
 for i,a in enumerate(source):
  b=source[(i+1)%len(source)]
  out.append((a[0]^b[1]^seed,(a[1]+b[2])&0xffffffff,a[2]^b[3],(a[3]+b[0]+seed)&0xffffffff))
 return out

def expected(trial,active,n=N):
 a=[(i*17+1,i*3+7,i^0x12345,i*13+11) for i in range(n)]
 untouched=[(0xa5a5a5a5,)*4 for _ in range(n)]
 b=list(untouched);c=list(untouched);n1=n2=0
 if active:
  if trial in (1,2,3):b=transform(a,0x3141);c=transform(b,0x1234);n1=n2=n
  elif trial==4:c=transform(b,0x1234);n2=n
  elif trial==5:c=transform(b,0x1234);b=transform(a,0x3141);n1=n2=n
 def array(rows):return b'\xa5'*64+b''.join(struct.pack('<4I',*r) for r in rows)+b'\xa5'*64
 def counter(value):return b'\xa5'*64+struct.pack('<I',value)+b'\xa5'*64
 return {'a':array(a),'b':array(b),'c':array(c),'count1':counter(n1),'count2':counter(n2)}

def verify(root):
 root=Path(root).resolve();i=read(root/'inputs.json');r=read(root/'results.json');m=read(root/'execution/manifest.json');lease=m['GPU_reservation'];scenario=i['case_index'];mode=i['mode']
 require(scenario in (0,1,2,3) and mode in ('prepare','execute') and r==read(root/'execution/execution.stdout') and r['status']=='PASS' and r['scenario']==scenario and r['mode']==mode and r['scope_restored'] and not r['system_modified'],'scope or scenario differs')
 require(r['device']=='NVIDIA GeForce GTX 880M' and r['registry_id']==i['registry_id'],'device differs')
 require(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and lease['state']=='terminal' and lease['child_PID']==m['pid']==r['pid'] and not lease['known_signed_processes_live'],'process not terminal')
 require(m['arguments']==[str(root/'assets/partial_buffer_stencil.metallib'),str(root/'assets/partial_buffer_stencil.json'),str(root/'outputs'),mode,str(i['registry_id']),str(scenario)],'arguments differ')
 require(sha(root/'assets/partial_buffer_stencil.metallib')==i['library_SHA256']==LIB and sha(root/'assets/partial_buffer_stencil.json')==i['manifest_SHA256']==MANIFEST,'shader identity differs')
 for name,h in i['frozen'].items():require(sha(root/name)==h,'frozen source differs: '+name)
 require(sha(root/'runtime_archive.a')==i['runtime_archive_SHA256'] and sha(root/'application')==i['executable_SHA256']==m['original_binary_sha256'] and sha(root/'execution/application')==m['signed_binary_sha256']==lease['signed_binary_sha256'],'artifact identity differs')
 require(m['launcher_SHA256']==i['frozen']['runtime/run_sdk_host.py'] and m['reservation_module_SHA256']==i['frozen']['runtime/lab_gpu_reservation.py'],'launcher identity differs')
 require({x['name'] for x in r['negative']}=={'later_short','too_many'} and len(r['negative'])==2 and all(not x['user_submitted'] for x in r['negative']),'negative controls differ')
 require(('Resident schema2 buffer range is insufficient' if scenario==1 else 'qualified resource envelope') in next(x['reason'] for x in r['negative'] if x['name']=='later_short') and 'exceeds 16 resident launches' in next(x['reason'] for x in r['negative'] if x['name']=='too_many'),'negative reasons differ')
 snap=r['snapshot_controls'];dest=0 if scenario==3 else 1;source=1-dest;require(snap['same_icb'] and snap['source_index']==source and snap['destination_index']==dest and snap['copy_event']['operation']=='CPU_snapshot_copy' and snap['copy_event']['source_location']==source and snap['copy_event']['destination_index']==dest and not snap['copy_event']['GPU_timeline_copy'],'overlap evidence differs');require(snap['disabled_refused'] and snap['bad_range_refused'] and snap['source_reset_before_execution'] and not snap['copy_submitted_user_work'] and snap['source_records_prepared']==(16 if scenario==3 else 3 if scenario in (1,2) else 4) and snap['materials_at_snapshot']==snap['source_records_prepared'],'snapshot controls differ')
 runs=r['runs'];require(len(runs)==(6 if mode=='execute' else 2),'trial count differs');outputs=0
 expected_materials=([ (0,0),(0,4),(4,4),(4,6),(6,6),(6,10) ] if scenario==0 else
                     [ (0,0),(0,3),(3,3),(3,4),(4,4),(4,7) ] if scenario==1 else
                     [ (0,0),(0,3),(3,3),(3,5),(5,5),(5,8) ] if scenario==2 else
                     [ (0,0),(0,16),(16,16),(16,24),(24,24),(24,40) ])
 for trial,row in enumerate(runs):
  require(row['trial']==trial and (row['materials_before'],row['materials_after'])==tuple(x+snap['materials_at_snapshot']-(1 if scenario in (1,2) and x>0 else 0) for x in expected_materials[trial]),'materialization/reuse differs')
  for suffix,active in [('pre',False)]+([('post',trial!=0)] if mode=='execute' else []):
   for name,wanted in expected(trial,active,385 if scenario==3 else N).items():require((root/'outputs'/f'trial-{trial}.{suffix}.{name}.bin').read_bytes()==wanted,f'raw output or guard differs: {trial} {suffix} {name}')
   if suffix=='post' and active:outputs+=(1 if trial==4 else 2)*(385 if scenario==3 else N)
  if trial in (1,2,3,5):
   e=row['event'];proof=e['evidence'];launches=16 if scenario==3 else 4 if scenario==0 else 3
   require(e['operation']=='execute_bounded_partial_range' and e['location']==dest and e['length']==3 and e['serial_wait_after_each_launch'] and not e['native_ICB'],'range event differs')
   require([x['index'] for x in e['slots']]==[dest,dest+2] and [x['first_launch'] for x in e['slots']]==([0,8] if scenario==3 else [0,1] if scenario==2 else [0,2]) and [x['launches'] for x in e['slots']]==([8,8] if scenario==3 else [1,2] if scenario==2 else [2,1] if scenario==1 else [2,2]) and [x['partial'] for x in e['slots']]==([False,True] if scenario==2 else [True,False] if scenario==1 else [True,True]),'slot mapping differs')
   require(proof['resident_launches']==launches and proof['owners']==launches and proof['command_bytes']==24*launches and len(set(proof['descriptor_GPU_addresses']))==launches and not proof['native_preparation_GPU_dispatches'] and not proof['CPU_constant_uploads_in_launch'],'resident stream differs')
  if mode=='execute':require(row['committed'] and row['command_status']==4 and row['restored_before_commit']==(trial==5),'commit/lifetime differs')
  else:require(not row['committed'],'prepare submitted user buffer')
 require(r['user_dispatches']==(9 if mode=='execute' else 0) and outputs==((3465 if scenario==3 else 864) if mode=='execute' else 0),'user work count differs')
 return {'status':'PASS','scenario':['partial_partial','partial_uniform','uniform_partial','partial_partial_3d_limit'][scenario],'mode':mode,'logical_dispatches':r['user_dispatches'],'invocations':outputs,'checked_output_words':outputs*4,'order_controls':2 if mode=='execute' else 0,'negative_preflight_controls':4,'same_buffer_overlap_direction':'backward' if scenario==3 else 'forward','snapshot_source_reset':True,'partial_cache_rematerialized':True,'uniform_cache_reused':scenario in (1,2),'all_children_terminal':True,'native_apple_ICB':False,'system_modified':False}
if __name__=='__main__':print(json.dumps(verify(sys.argv[1]),sort_keys=True))
