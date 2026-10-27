#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent raw oracle for the opted-in fixed-profile partial ICB path."""
import hashlib,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from verify_partial_assembly_3d import expected_outputs
LIB='1e89eaf47bdcb482e4fc760869b6005e47c1e836ec43e14820ba601c28fdd3f5'
MANIFEST='31287315ccb87740c86c7180651007a766535bfcadf3de34edbe10e6bad233be'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require(ok,why):
 if not ok:raise ValueError(why)
def verify(root):
 p=Path(root).resolve();i=read(p/'inputs.json');r=read(p/'results.json');m=read(p/'execution/manifest.json');lease=m['GPU_reservation'];mode=i['mode']
 require(mode in ('prepare','execute') and r==read(p/'execution/execution.stdout') and r['mode']==mode and r['status']=='PASS' and r['scope_restored'] and not r['system_modified'] and not r['driver_modified'],'scope/result differs')
 require(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and lease['state']=='terminal' and lease['exit_code']==0 and lease['child_PID']==m['pid']==r['pid'] and not lease['known_signed_processes_live'],'host/reservation not terminal')
 require(m['arguments']==[str(p/'assets/partial_wide_barrier.metallib'),str(p/'assets/partial_wide_barrier.json'),str(p/'outputs'),mode,str(i['registry_id'])] and r['registry_id']==i['registry_id'] and r['device']=='NVIDIA GeForce GTX 880M','host arguments or GPU differs')
 require(sha(p/'assets/partial_wide_barrier.metallib')==i['library_SHA256']==LIB and sha(p/'assets/partial_wide_barrier.json')==i['manifest_SHA256']==MANIFEST,'library/manifest differs')
 for name,h in i['frozen'].items():require(sha(p/name)==h,'frozen input differs: '+name)
 require(sha(p/'runtime_archive.a')==i['runtime_archive_SHA256'] and sha(p/'application')==m['original_binary_sha256']==i['executable_SHA256'] and sha(p/'execution/application')==m['signed_binary_sha256']==lease['signed_binary_sha256'],'archive/host differs')
 require(m['launcher_SHA256']==i['frozen']['runtime/run_sdk_host.py'] and m['reservation_module_SHA256']==i['frozen']['runtime/lab_gpu_reservation.py'],'launcher differs')
 require(set(r['rejections'])=={'disabled','wrong_grid','wrong_local','copy','mixed_range','alias','short_buffer'} and len(r['rejections'])==7,'negative controls differ')
 reasons=r['rejection_reasons'];expected={'disabled':'explicitly enabled certified pipeline','wrong_grid':'Partial or zero thread grids','wrong_local':'Partial or zero thread grids','copy':'experimental partial command','mixed_range':'one command in a serial range','alias':'exact, nonaliasing qualified resource envelope','short_buffer':'exact, nonaliasing qualified resource envelope'}
 require(set(reasons)==set(expected) and all(expected[k] in reasons[k] for k in expected),'negative rejection reasons differ')
 count=5 if mode=='execute' else 2;runs=r['runs'];require(len(runs)==count,'trial count differs');rows=[];total=0
 for trial,row in enumerate(runs):
  require(row['trial']==trial and row['materializations_before']==[0,0,8,8,16][trial] and row['materializations_after']==[0,8,8,16,24][trial],'cache/invalidation differs')
  for suffix,number in [('pre',0)]+([('post',9 if trial else 0)] if mode=='execute' else []):
   c,g,counter,n=expected_outputs(number);prefix=p/'outputs'/f'trial-{trial}.{suffix}'
   for name,wanted in [('coordinates',c),('geometry',g),('counter',counter)]:require(Path(str(prefix)+'.'+name+'.bin').read_bytes()==wanted,'GPU output or guard differs: '+str(trial)+' '+suffix+' '+name)
   if suffix=='post':total+=n;rows.append({'trial':trial,'threads':n,'coordinates_SHA256':sha(str(prefix)+'.coordinates.bin'),'geometry_SHA256':sha(str(prefix)+'.geometry.bin')})
  if trial:
   proof=row['proof'];require(proof['resident_launches']==8 and proof['command_bytes']==192 and proof['owners']==8 and proof['native_preparation_GPU_dispatches']==0 and proof['CPU_constant_uploads_in_launch']==0 and len(set(proof['descriptor_GPU_addresses']))==8,'resident sequence differs')
   require(all(x['original_record_function']=='partial_builtin_barrier' and x['native_register_count']==22 and x['static_threadgroup_bytes']==512 for x in proof['owner_original_profiles']),'resident profile differs')
  if mode=='execute':require(row['committed'] and row['command_status']==4 and row['scope_restored_before_commit']==(trial==4),'commit or lifetime differs')
  else:require(not row['committed'],'prepare submitted user command')
 require(r['user_command_buffers']==(4 if mode=='execute' else 0),'command-buffer count differs')
 return {'verification':'PASS','mode':mode,'user_command_buffers':r['user_command_buffers'],'threads':total,'uint32_values_checked':total*8,'negative_cases':len(r['rejections']),'rows':rows,'partial_ICB_fixed_profile':True,'native_apple_ICB':False,'transparent_integration':False,'system_modified':False}
if __name__=='__main__':print(json.dumps(verify(sys.argv[1]),sort_keys=True))
