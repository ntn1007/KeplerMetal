#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent raw-output oracle for one fixed eight-region 3D grid experiment."""
import hashlib,json,struct,sys
from pathlib import Path
LIB='1e89eaf47bdcb482e4fc760869b6005e47c1e836ec43e14820ba601c28fdd3f5'
MANIFEST='31287315ccb87740c86c7180651007a766535bfcadf3de34edbe10e6bad233be'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(ok,why):
 if not ok:raise ValueError(why)
def pack(v):return v[0]|v[1]<<10|v[2]<<20

def expected_outputs(trial):
 require(trial in range(11),'Unknown trial')
 coords=bytearray(b'\xa5'*(1024*16+128));geom=bytearray(coords);counter=bytearray(b'\xa5'*132);n=0;seed=0x3141
 for z in range(5):
  for y in range(7):
   for x in range(11):
    gid=(x,y,z);group=(x//4,y//4,z//3);segment=(4 if group[0]==2 else 0)|(2 if group[1]==1 else 0)|(1 if group[2]==1 else 0)
    if trial==0 or 1<=trial<=8 and segment!=trial-1:continue
    local=(x%4,y%4,z%3);actual=(min(4,11-group[0]*4),min(4,7-group[1]*4),min(3,5-group[2]*3))
    lane=local[0]+actual[0]*(local[1]+actual[1]*local[2]);size=actual[0]*actual[1]*actual[2];witness=((lane+32)%size)^seed;index=x+11*(y+7*z)
    struct.pack_into('<4I',coords,64+index*16,pack(gid),pack(local),pack(group),pack((3,2,2)))
    struct.pack_into('<4I',geom,64+index*16,pack(actual),pack((4,4,3)),pack((11,7,5)),witness);n+=1
 struct.pack_into('<I',counter,64,n)
 return bytes(coords),bytes(geom),bytes(counter),n

def verify(root):
 p=Path(root).resolve();i=read(p/'inputs.json');r=read(p/'results.json');m=read(p/'execution/manifest.json');lease=m['GPU_reservation'];mode=i['mode']
 require(mode in ('prepare','execute') and r==read(p/'execution/execution.stdout') and r['mode']==mode and r['status']=='PASS' and r['scope_restored'] and not r['system_modified'] and not r['driver_modified'] and not r['shader_modified'] and not r['partial_threadgroups_implemented'],'scope/result differs')
 require(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and lease['state']=='terminal' and lease['exit_code']==0 and lease['child_PID']==m['pid']==r['pid'] and not lease['known_signed_processes_live'],'host/reservation not terminal')
 require(m['arguments']==[str(p/'assets/partial_wide_barrier.metallib'),str(p/'assets/partial_wide_barrier.json'),str(p/'outputs'),mode,str(i['registry_id'])] and r['registry_id']==i['registry_id'] and r['device']=='NVIDIA GeForce GTX 880M','host arguments or GPU differs')
 require(sha(p/'assets/partial_wide_barrier.metallib')==i['library_SHA256']==LIB and sha(p/'assets/partial_wide_barrier.json')==i['manifest_SHA256']==MANIFEST,'library/manifest differs')
 for name,h in i['frozen'].items():require(sha(p/name)==h,'frozen input differs: '+name)
 require(sha(p/'runtime_archive.a')==i['runtime_archive_SHA256'] and sha(p/'application')==m['original_binary_sha256']==i['executable_SHA256'] and sha(p/'execution/application')==m['signed_binary_sha256']==lease['signed_binary_sha256'],'archive/host differs')
 require(m['launcher_SHA256']==i['frozen']['runtime/run_sdk_host.py'] and m['reservation_module_SHA256']==i['frozen']['runtime/lab_gpu_reservation.py'],'launcher differs')
 out=p/'outputs';states=[];qmds=[];addresses=[];streams=[]
 for node in range(8):
  before=(out/f'record-{node}.baseline.constants.bin').read_bytes();after=(out/f'record-{node}.constants.bin').read_bytes();q=(out/f'record-{node}.qmd.bin').read_bytes();relocated=(out/f'record-{node}.relocated.bin').read_bytes()
  require(len(before)==len(after)==65536 and len(q)==4096 and len(relocated)==464 and q[:256]==relocated[184:440],'baseline/QMD differs')
  base=bytearray(before)
  for off,v in ((0x710,(8 if node&4 else 0,4 if node&2 else 0,3 if node&1 else 0)),(0x720,(11,7,5)),(0x730,(4,4,3)),(0x740,(3,2,2))):struct.pack_into('<3I',base,off,*v)
  require(bytes(base)==after and before[0x710:0x71c]==bytes(12),'constant changes differ')
  word=lambda off:struct.unpack_from('<I',q,off)[0]
  require(word(0x30)==(1 if node&4 else 2) and word(0x34)==0x10001 and word(0x48)>>16==(3 if node&4 else 4) and word(0x4c)==((3 if node&2 else 4)|((2 if node&1 else 3)<<16)) and word(0x44)&0x3ffff==512 and word(0xb8)>>24==22 and word(0x50)&255==6,'QMD geometry differs')
  states.append(after);qmds.append(q);streams.append(relocated[440:464]);addresses.append(struct.unpack_from('<I',relocated,444)[0]<<8)
 require(len(set(addresses))==8,'resident QMD aliases')
 total=words=0;rows=[];runs=r['runs'];require(len(runs)==(11 if mode=='execute' else 1),'unexpected trial count')
 for trial,row in enumerate(runs):
  require(row['trial']==trial,'trial identity differs');order=(0,) if trial==0 else (trial-1,) if trial<=8 else tuple(range(8)) if trial==9 else tuple(reversed(range(8)));suppress=trial==0;proof=row['proof']
  stream=bytearray().join(streams[n] for n in order)
  if suppress:struct.pack_into('<2I',stream,8,0x20012040,0)
  require(proof['command_bytes']==len(stream) and proof['resident_launches']==len(order) and proof['native_preparation_GPU_dispatches']==0 and proof['CPU_constant_uploads_in_launch']==0 and proof['launch_suppressed']==suppress and proof['descriptor_GPU_addresses']==[addresses[n] for n in order] and proof['stream_SHA256']==hashlib.sha256(stream).hexdigest(),'resident stream evidence differs')
  if mode=='prepare':require(not row['committed'] and r['user_dispatches']==0,'prepare submitted user work');continue
  require(row['committed'] and row['command_status']==4,'user command failed');prefix=out/f'trial-{trial}'
  for node in range(8):require(Path(str(prefix)+f'.record-{node}.constants.bin').read_bytes()==states[node] and Path(str(prefix)+f'.record-{node}.qmd.bin').read_bytes()==qmds[node],'resident state changed')
  c,g,counter,n=expected_outputs(trial)
  for name,wanted in [('coordinates',c),('geometry',g),('counter',counter)]:require(Path(str(prefix)+'.'+name+'.bin').read_bytes()==wanted,'GPU result/guard differs: '+str(trial)+' '+name)
  total+=n;words+=8*n;rows.append({'trial':trial,'threads':n,'coordinates_SHA256':sha(str(prefix)+'.coordinates.bin'),'geometry_SHA256':sha(str(prefix)+'.geometry.bin')})
 require(r['user_dispatches']==(24 if mode=='execute' else 0),'dispatch count differs')
 if mode=='execute':require(rows[9]['coordinates_SHA256']==rows[10]['coordinates_SHA256'] and rows[9]['geometry_SHA256']==rows[10]['geometry_SHA256'],'order changes outputs')
 return {'verification':'PASS','mode':mode,'user_dispatches':r['user_dispatches'],'threads':total,'uint32_values_checked':words,'rows':rows,'eight_region_logical_grid':[11,7,5],'native_ICB_or_transparent_integration':False,'system_modified':False}
if __name__=='__main__':print(json.dumps(verify(sys.argv[1]),sort_keys=True))
