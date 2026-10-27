#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent oracle for the exact, bounded resident edge-builtins experiment."""
import hashlib,json,math,struct,sys
from pathlib import Path
LIB='83a3f8919c550e6cb4ffa0ab238b233ed5a088214e5a06120770866b053750ca'
MANIFEST='77f2e76f9c244fa3387f2afbd9c0b6e9b2592660bc763f41b8617a0cf7c1251d'
GROUPS=((1,1,1),(1,1,1),(1,1,1))
LOCAL=((3,1,1),(4,1,1),(4,2,1))
NOMINAL=((4,1,1),(4,2,1),(4,2,2))
LOGICAL_GROUPS=((3,1,1),(2,3,1),(2,2,3))
LOGICAL_GRID=((11,1,1),(8,5,1),(8,4,5))
ORIGINS=((8,0,0),(0,4,0),(0,0,4))

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def require(ok,why):
 if not ok:raise ValueError(why)
def pack(v):return v[0]|v[1]<<10|v[2]<<20

def expected_outputs(node,origin,suppress):
 require(0<=node<3 and origin in ((0,0,0),ORIGINS[node]),'unqualified test geometry')
 physical,l=GROUPS[node],LOCAL[node];shifted=origin!=(0,0,0);g=LOGICAL_GROUPS[node] if shifted else physical;nominal=NOMINAL[node] if shifted else l;full=tuple(a*b for a,b in zip(physical,l));stride=tuple(a*b for a,b in zip(g,l));n=math.prod(full)
 coordinates=bytearray(b'\xa5'*(1024*16+128));geometry=bytearray(coordinates);counter=bytearray(b'\xa5'*132);struct.pack_into('<I',counter,64,0 if suppress else n)
 seen=set()
 if not suppress:
  for z in range(full[2]):
   for y in range(full[1]):
    for x in range(full[0]):
     position=(x,y,z);gid=tuple(a+b for a,b in zip(position,origin));grid=LOGICAL_GRID[node] if shifted else full;index=gid[0]+grid[0]*(gid[1]+grid[1]*gid[2]);require(index<1024 and index not in seen,'bad shader output addressing');seen.add(index)
     lane=tuple(a%b for a,b in zip(position,l));group=tuple(a//b for a,b in zip(gid,nominal));seed=0x3141+101*node
     lane_index=lane[0]+l[0]*(lane[1]+l[1]*lane[2]);witness=((lane_index+1)%math.prod(l))^seed
     struct.pack_into('<4I',coordinates,64+index*16,pack(gid),pack(lane),pack(group),pack(g));struct.pack_into('<4I',geometry,64+index*16,pack(l),pack(nominal),pack(grid),witness)
 return bytes(coordinates),bytes(geometry),bytes(counter),n

def verify(root):
 p=Path(root).resolve();i=read(p/'inputs.json');r=read(p/'results.json');m=read(p/'execution/manifest.json');lease=m['GPU_reservation'];mode=i['mode']
 require(mode in ('prepare','execute') and r==read(p/'execution/execution.stdout') and r['mode']==mode and r['status']=='PASS' and r['scope_restored'] and not r['system_modified'] and not r['driver_modified'] and not r['shader_modified'] and not r['partial_threadgroups_implemented'],'scope or result differs')
 require(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and lease['state']=='terminal' and lease['exit_code']==0 and lease['child_PID']==m['pid']==r['pid'] and not lease['known_signed_processes_live'],'host or reservation not successfully terminal')
 require(m['arguments']==[str(p/'assets/partial_builtin_barrier.metallib'),str(p/'assets/partial_builtin_barrier.json'),str(p/'outputs'),mode,str(i['registry_id'])] and r['registry_id']==i['registry_id'] and r['device']=='NVIDIA GeForce GTX 880M','host arguments or GPU differs')
 require(sha(p/'assets/partial_builtin_barrier.metallib')==i['library_SHA256']==LIB and sha(p/'assets/partial_builtin_barrier.json')==i['manifest_SHA256']==MANIFEST,'library/manifest differs')
 for name,h in i['frozen'].items():require(sha(p/name)==h,'frozen input differs: '+name)
 require(sha(p/'runtime_archive.a')==i['runtime_archive_SHA256'] and sha(p/'application')==m['original_binary_sha256']==i['executable_SHA256'] and sha(p/'execution/application')==m['signed_binary_sha256']==lease['signed_binary_sha256'],'archive/host differs')
 require(m['launcher_SHA256']==i['frozen']['runtime/run_sdk_host.py'] and m['reservation_module_SHA256']==i['frozen']['runtime/lab_gpu_reservation.py'],'launcher differs')
 o=p/'outputs';baselines=[];qmds=[]
 for node in range(3):
  base=(o/f'baseline-{node}.constants.bin').read_bytes();q=(o/f'baseline-{node}.qmd.bin').read_bytes();require(len(base)==65536 and len(q)==4096 and base[0x710:0x71c]==bytes(12),'baseline origin/QMD differs');baselines.append(base);qmds.append(q)
 total=0;words=0;controls=0;rows=[];runs=r['runs'];require(len(runs)==(7 if mode=='execute' else 1),'unexpected trial count')
 for trial,row in enumerate(runs):
  node=0 if trial==0 else (trial-1)//2;suppress=trial==0;shifted=trial>=2 and trial%2==0;origin=ORIGINS[node] if shifted else (0,0,0)
  require(row['trial']==trial and row['node']==node and row['suppressed']==suppress,'trial identity differs');proof=row['proof'];require(proof['command_bytes']==24 and proof['resident_launches']==1 and proof['native_preparation_GPU_dispatches']==0 and proof['CPU_constant_uploads_in_launch']==0 and proof['launch_suppressed']==suppress,'resident launch proof differs')
  base=bytearray(baselines[node]);
  if shifted:
   for offset,values in ((0x710,origin),(0x720,LOGICAL_GRID[node]),(0x730,NOMINAL[node]),(0x740,LOGICAL_GROUPS[node])):struct.pack_into('<3I',base,offset,*values)
  prefix=o/f'trial-{trial}';before=Path(str(prefix)+'.before.constants.bin').read_bytes();q=Path(str(prefix)+'.before.qmd.bin').read_bytes();require(before==base and q==qmds[node],'unexpected modified state')
  if mode=='prepare':require(not row['committed'] and r['user_dispatches']==0,'prepare submitted user kernel');continue
  require(row['committed'] and row['command_status']==4 and row['origin']==list(origin),'command status/origin differs')
  require(Path(str(prefix)+'.after.constants.bin').read_bytes()==before and Path(str(prefix)+'.after.qmd.bin').read_bytes()==q and sha(str(prefix)+'.before.constants.bin')==row['constants_SHA256'] and sha(str(prefix)+'.before.qmd.bin')==row['QMD_SHA256'],'resident state changed')
  c,g,counter,n=expected_outputs(node,origin,suppress)
  for name,wanted in [('coordinates',c),('geometry',g),('counter',counter)]:require(Path(str(prefix)+'.'+name+'.bin').read_bytes()==wanted,'GPU numerical value or guard differs: '+str(trial)+' '+name)
  total+=0 if suppress else n;words+=0 if suppress else 8*n;controls+=int(suppress);rows.append({'node':node,'origin':list(origin),'threads':0 if suppress else n,'output_SHA256':sha(str(prefix)+'.coordinates.bin'),'geometry_SHA256':sha(str(prefix)+'.geometry.bin')})
 require(r['user_dispatches']==(6 if mode=='execute' else 0),'dispatch count differs')
 return {'verification':'PASS','mode':mode,'user_dispatches':r['user_dispatches'],'threads':total,'uint32_values_checked':words,'suppressed_controls':controls,'rows':rows,'GPU_execution_proved':mode=='execute','partial_threadgroups_implemented':False,'builtin_constants_experimental':True}
if __name__=='__main__':print(json.dumps(verify(sys.argv[1]),sort_keys=True))
