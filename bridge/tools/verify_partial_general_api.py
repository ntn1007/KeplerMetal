#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent CPU oracle for bounded, opted-in partial-grid ICB execution."""
import hashlib,json,math,struct,sys
from pathlib import Path
LIB='1e89eaf47bdcb482e4fc760869b6005e47c1e836ec43e14820ba601c28fdd3f5'
MANIFEST='31287315ccb87740c86c7180651007a766535bfcadf3de34edbe10e6bad233be'
CASES=[((11,7,5),(4,4,3),8),((191,1,1),(64,1,1),2),((13,5,2),(4,3,2),4),((3,2,1),(4,4,3),1),((10,9,3),(4,4,2),8),((13,4,4),(4,4,4),3),((1023,1,1),(4,1,1),9),((1,1,1),(128,1,1),1)]
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(ok,why):
 if not ok:raise ValueError(why)
def pack(v):return v[0]|v[1]<<10|v[2]<<20

def expected_outputs(case,active):
 require(type(case) is int and 0<=case<len(CASES),'Unknown case');grid,local,_=CASES[case];groups=tuple((g+l-1)//l for g,l in zip(grid,local));n=math.prod(grid)
 coords=bytearray(b'\xa5'*(1024*16+128));geom=bytearray(coords);counter=bytearray(b'\xa5'*132)
 struct.pack_into('<I',counter,64,n if active else 0)
 if active:
  for z in range(grid[2]):
   for y in range(grid[1]):
    for x in range(grid[0]):
     gid=(x,y,z);group=tuple(v//l for v,l in zip(gid,local));lane=tuple(v%l for v,l in zip(gid,local));actual=tuple(min(l,g-k*l) for g,l,k in zip(grid,local,group))
     lane_index=lane[0]+actual[0]*(lane[1]+actual[1]*lane[2]);witness=((lane_index+32)%math.prod(actual))^0x3141;index=x+grid[0]*(y+grid[1]*z)
     struct.pack_into('<4I',coords,64+16*index,pack(gid),pack(lane),pack(group),pack(groups));struct.pack_into('<4I',geom,64+16*index,pack(actual),pack(local),pack(grid),witness)
 return bytes(coords),bytes(geom),bytes(counter),n if active else 0

def verify(root):
 p=Path(root).resolve();i=read(p/'inputs.json');r=read(p/'results.json');m=read(p/'execution/manifest.json');lease=m['GPU_reservation'];mode=i['mode'];case=i['case_index'];grid,local,regions=CASES[case]
 require(mode in ('prepare','execute') and r==read(p/'execution/execution.stdout') and r['mode']==mode and r['status']=='PASS' and r['scope_restored'] and not r['system_modified'] and not r['driver_modified'] and r['case_index']==case and r['grid']==list(grid) and r['local']==list(local),'scope or case differs')
 require(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and lease['state']=='terminal' and lease['exit_code']==0 and lease['child_PID']==m['pid']==r['pid'] and not lease['known_signed_processes_live'],'host/reservation not terminal')
 require(m['arguments']==[str(p/'assets/partial_wide_barrier.metallib'),str(p/'assets/partial_wide_barrier.json'),str(p/'outputs'),mode,str(i['registry_id']),str(case)] and r['registry_id']==i['registry_id'] and r['device']=='NVIDIA GeForce GTX 880M','host arguments or GPU differs')
 require(sha(p/'assets/partial_wide_barrier.metallib')==i['library_SHA256']==LIB and sha(p/'assets/partial_wide_barrier.json')==i['manifest_SHA256']==MANIFEST,'library/manifest differs')
 for name,h in i['frozen'].items():require(sha(p/name)==h,'frozen input differs: '+name)
 require(sha(p/'runtime_archive.a')==i['runtime_archive_SHA256'] and sha(p/'application')==m['original_binary_sha256']==i['executable_SHA256'] and sha(p/'execution/application')==m['signed_binary_sha256']==lease['signed_binary_sha256'],'archive/host differs')
 require(m['launcher_SHA256']==i['frozen']['runtime/run_sdk_host.py'] and m['reservation_module_SHA256']==i['frozen']['runtime/lab_gpu_reservation.py'],'launcher differs')
 expected={'disabled':'explicitly enabled certified pipeline','wrong_grid':'packed dimension bounds','wrong_local':'invocation, local or region bounds','copy':'experimental partial command','resident_export':'Partial grid cannot enter ordinary resident selection or copying','mixed_range':'one command in a serial range','alias':'exact, nonaliasing qualified resource envelope','short_buffer':'exact, nonaliasing qualified resource envelope'}
 require(set(r['rejections'])==set(expected) and len(r['rejections'])==8 and set(r['rejection_reasons'])==set(expected) and all(expected[k] in r['rejection_reasons'][k] for k in expected),'negative controls differ')
 runs=r['runs'];require(len(runs)==(5 if mode=='execute' else 2),'trial count differs');total=0;rows=[]
 for trial,row in enumerate(runs):
  require(row['trial']==trial and row['materializations_before']==[0,0,regions,regions,regions*2][trial] and row['materializations_after']==[0,regions,regions,regions*2,regions*3][trial],'cache/invalidation differs')
  for suffix,active in [('pre',False)]+([('post',trial!=0)] if mode=='execute' else []):
   c,g,counter,n=expected_outputs(case,active);prefix=p/'outputs'/f'trial-{trial}.{suffix}'
   for name,wanted in [('coordinates',c),('geometry',g),('counter',counter)]:require(Path(str(prefix)+'.'+name+'.bin').read_bytes()==wanted,'GPU value/guard differs: '+str(case)+' '+str(trial)+' '+suffix+' '+name)
   if suffix=='post':total+=n;rows.append({'trial':trial,'threads':n,'coordinates_SHA256':sha(str(prefix)+'.coordinates.bin'),'geometry_SHA256':sha(str(prefix)+'.geometry.bin')})
  if trial:
   proof=row['proof'];require(proof['resident_launches']==regions and proof['command_bytes']==24*regions and proof['owners']==regions and proof['native_preparation_GPU_dispatches']==0 and proof['CPU_constant_uploads_in_launch']==0 and len(set(proof['descriptor_GPU_addresses']))==regions,'resident sequence differs')
   for x in proof['owner_original_profiles']:
    require(x['original_record_function']=='partial_builtin_barrier' and x['native_register_count']==22 and x['static_threadgroup_bytes']==512 and math.prod(x['groups_shape'])*math.prod(x['local_shape'])<=128,'resident profile differs')
  if mode=='execute':require(row['committed'] and row['command_status']==4 and row['scope_restored_before_commit']==(trial==4),'commit or lifetime differs')
  else:require(not row['committed'],'prepare submitted user command')
 require(r['user_command_buffers']==(4 if mode=='execute' else 0),'command-buffer count differs')
 return {'verification':'PASS','mode':mode,'case':case,'grid':list(grid),'local':list(local),'regions':regions,'user_command_buffers':r['user_command_buffers'],'threads':total,'uint32_values_checked':total*8,'negative_cases':len(expected),'rows':rows,'bounded_partial_ICB':True,'native_apple_ICB':False,'transparent_integration':False,'system_modified':False}
if __name__=='__main__':print(json.dumps(verify(sys.argv[1]),sort_keys=True))
