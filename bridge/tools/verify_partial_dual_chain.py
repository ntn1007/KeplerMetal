#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU oracle for two serial partial/uniform producer-consumer ICB slots."""
import hashlib,json,struct,sys
from pathlib import Path
LIB='0985a3057cd487352d801abcd180bf05a681b8dc7357ee5400db044098c32c4c'
MANIFEST='c7dcdc81adba7f7ba6cf8175ecc179a086a9bd150b44d71ca1a39ad18846ef9a'
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

def expected(trial,active,scenario):
 grid=(11,7,5) if scenario==3 else (96,1,1)
 first=(4,4,3) if scenario==3 else (32 if scenario==2 else 65,1,1)
 second=(4,4,3) if scenario==3 else (32 if scenario==1 else 37,1,1)
 n=grid[0]*grid[1]*grid[2]
 a=[(i*17+1,i*3+7,i^0x12345,i*13+11) for i in range(n)]
 untouched=[(0xa5a5a5a5,)*4 for _ in range(n)]
 b=list(untouched);geo=list(untouched);c=list(untouched);n1=n2=0
 def producer(local):
  coords=[];geometry=[];groups=tuple((g+l-1)//l for g,l in zip(grid,local))
  def pack(v):return v[0]|(v[1]<<10)|(v[2]<<20)
  for z in range(grid[2]):
   for y in range(grid[1]):
    for x in range(grid[0]):
     gid=(x,y,z);group=tuple(v//l for v,l in zip(gid,local));lane=tuple(v%l for v,l in zip(gid,local));actual=tuple(min(l,g-k*l) for g,l,k in zip(grid,local,group))
     idx=lane[0]+actual[0]*(lane[1]+actual[1]*lane[2]);size=actual[0]*actual[1]*actual[2]
     coords.append((pack(gid),pack(lane),pack(group),pack(groups)));geometry.append((pack(actual),pack(local),pack(grid),((idx+32)%size)^0x3141))
  return coords,geometry
 if active:
  if trial in (1,2,3):b,geo=producer(first);c=transform(b,0x1234);n1=n2=n
  elif trial==4:c=transform(b,0x1234);n2=n
  elif trial==5:c=transform(b,0x1234);b,geo=producer(second);n1=n2=n
 def array(rows):return b'\xa5'*64+b''.join(struct.pack('<4I',*r) for r in rows)+b'\xa5'*64
 def counter(value):return b'\xa5'*64+struct.pack('<I',value)+b'\xa5'*64
 return {'a':array(a),'b':array(b),'geo':array(geo),'c':array(c),'count1':counter(n1),'count2':counter(n2)}

def verify(root):
 root=Path(root).resolve();i=read(root/'inputs.json');r=read(root/'results.json');m=read(root/'execution/manifest.json');lease=m['GPU_reservation'];scenario=i['case_index'];mode=i['mode']
 require(scenario in (0,1,2,3) and mode in ('prepare','execute') and r==read(root/'execution/execution.stdout') and r['status']=='PASS' and r['scenario']==scenario and r['mode']==mode and r['scope_restored'] and not r['system_modified'],'scope or scenario differs')
 require(r['device']=='NVIDIA GeForce GTX 880M' and r['registry_id']==i['registry_id'],'device differs')
 require(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and lease['state']=='terminal' and lease['child_PID']==m['pid']==r['pid'] and not lease['known_signed_processes_live'],'process not terminal')
 require(m['arguments']==[str(root/'assets/partial_dual.metallib'),str(root/'assets/partial_dual.json'),str(root/'outputs'),mode,str(i['registry_id']),str(scenario)],'arguments differ')
 require(sha(root/'assets/partial_dual.metallib')==i['library_SHA256']==LIB and sha(root/'assets/partial_dual.json')==i['manifest_SHA256']==MANIFEST,'shader identity differs')
 for name,h in i['frozen'].items():require(sha(root/name)==h,'frozen source differs: '+name)
 require(sha(root/'runtime_archive.a')==i['runtime_archive_SHA256'] and sha(root/'application')==i['executable_SHA256']==m['original_binary_sha256'] and sha(root/'execution/application')==m['signed_binary_sha256']==lease['signed_binary_sha256'],'artifact identity differs')
 require(m['launcher_SHA256']==i['frozen']['runtime/run_sdk_host.py'] and m['reservation_module_SHA256']==i['frozen']['runtime/lab_gpu_reservation.py'],'launcher identity differs')
 require({x['name'] for x in r['negative']}=={'later_short','too_many'} and len(r['negative'])==2 and all(not x['user_submitted'] for x in r['negative']),'negative controls differ')
 require(('Resident schema2 buffer range is insufficient' if scenario==1 else 'qualified resource envelope') in next(x['reason'] for x in r['negative'] if x['name']=='later_short') and 'exceeds 16 resident launches' in next(x['reason'] for x in r['negative'] if x['name']=='too_many'),'negative reasons differ')
 runs=r['runs'];require(len(runs)==(6 if mode=='execute' else 2),'trial count differs');outputs=0
 expected_materials=([ (0,0),(0,4),(4,4),(4,6),(6,6),(6,10) ] if scenario==0 else
                     [ (0,0),(0,3),(3,3),(3,4),(4,4),(4,7) ] if scenario==1 else
                     [ (0,0),(0,3),(3,3),(3,5),(5,5),(5,8) ] if scenario==2 else
                     [ (0,0),(0,16),(16,16),(16,24),(24,24),(24,40) ])
 for trial,row in enumerate(runs):
  require(row['trial']==trial and (row['materials_before'],row['materials_after'])==expected_materials[trial],'materialization/reuse differs')
  for suffix,active in [('pre',False)]+([('post',trial!=0)] if mode=='execute' else []):
   for name,wanted in expected(trial,active,scenario).items():require((root/'outputs'/f'trial-{trial}.{suffix}.{name}.bin').read_bytes()==wanted,f'raw output or guard differs: {trial} {suffix} {name}')
   if suffix=='post' and active:outputs+=(1 if trial==4 else 2)*(385 if scenario==3 else N)
  if trial in (1,2,3,5):
   e=row['event'];proof=e['evidence'];launches=16 if scenario==3 else 4 if scenario==0 else 3
   require(e['operation']=='execute_bounded_partial_range' and e['location']==0 and e['length']==3 and e['serial_wait_after_each_launch'] and not e['native_ICB'],'range event differs')
   require([x['index'] for x in e['slots']]==[0,2] and [x['first_launch'] for x in e['slots']]==([0,8] if scenario==3 else [0,1] if scenario==2 else [0,2]) and [x['launches'] for x in e['slots']]==([8,8] if scenario==3 else [1,2] if scenario==2 else [2,1] if scenario==1 else [2,2]) and [x['partial'] for x in e['slots']]==([False,True] if scenario==2 else [True,False] if scenario==1 else [True,True]),'slot mapping differs')
   require(proof['resident_launches']==launches and proof['owners']==launches and proof['command_bytes']==24*launches and len(set(proof['descriptor_GPU_addresses']))==launches and not proof['native_preparation_GPU_dispatches'] and not proof['CPU_constant_uploads_in_launch'],'resident stream differs')
   profiles=proof['owner_original_profiles'];first_count=e['slots'][0]['launches'];expected_names=(['partial_buffer_stencil']*first_count+['partial_builtin_barrier']*(launches-first_count)) if trial==5 else (['partial_builtin_barrier']*first_count+['partial_buffer_stencil']*(launches-first_count))
   require([x['original_record_function'] for x in profiles]==expected_names and all(x['static_threadgroup_bytes']==(512 if x['original_record_function']=='partial_builtin_barrier' else 0) and x['native_register_count']==(22 if x['original_record_function']=='partial_builtin_barrier' else 11) for x in profiles),'cross-pipeline identities differ')
  if mode=='execute':require(row['committed'] and row['command_status']==4 and row['restored_before_commit']==(trial==5),'commit/lifetime differs')
  else:require(not row['committed'],'prepare submitted user buffer')
 require(r['user_dispatches']==(9 if mode=='execute' else 0) and outputs==((3465 if scenario==3 else 864) if mode=='execute' else 0),'user work count differs')
 return {'status':'PASS','scenario':['partial_partial','partial_uniform','uniform_partial','partial_partial_3d_limit'][scenario],'mode':mode,'logical_dispatches':r['user_dispatches'],'invocations':outputs,'checked_output_words':outputs*4,'order_controls':2 if mode=='execute' else 0,'negative_preflight_controls':2,'all_children_terminal':True,'native_apple_ICB':False,'system_modified':False}
if __name__=='__main__':print(json.dumps(verify(sys.argv[1]),sort_keys=True))
