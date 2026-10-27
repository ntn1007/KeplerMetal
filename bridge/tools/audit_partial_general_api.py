#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit bounded multi-shape ICB execution and same-runtime regressions."""
import datetime,hashlib,json,math,struct,subprocess,sys
from pathlib import Path
from verify_partial_general_api import verify,read,sha,CASES,pack
from verify_uniform_icb_3d import verify as verify_uniform
from verify_partial_icb_api import verify as verify_fixed
from verify_partial_assembly import verify as verify_1d
from verify_partial_grid_m1 import verify as verify_m1

def audit(paths):
 if len(paths)!=18:raise ValueError('Preparation, eight cases, two uniform hosts, references and four repeats required')
 paths=[Path(p).resolve() for p in paths];items=[];regressions=[]
 for index,p in enumerate(paths[:9]):
  v=verify(p);i=read(p/'inputs.json');m=read(p/'execution/manifest.json');d=read(p/'results.json');want=0 if index==0 else index-1
  if v!=read(p/'verification.stdout') or read(p/'verification-execution.json')!={'exit_code':0,'isolated_interpreter':True} or v['mode']!=('prepare' if index==0 else 'execute') or v['case']!=want:raise ValueError('Partial host qualification differs')
  subprocess.run(['codesign','--verify','--strict',str(p/'execution/application')],check=True,capture_output=True,timeout=15)
  for row in d['runs']:
   if row['trial']==0:continue
   proof=row['proof'];stream=bytearray();owners=proof['owner_original_profiles'];addrs=proof['descriptor_GPU_addresses']
   if len(owners)!=v['regions'] or len({x['registration_id'] for x in owners})!=1:raise ValueError('Partial owner registration differs')
   for owner,addr in zip(owners,addrs):
    if owner['descriptor_GPU_address']!=addr or addr%256 or addr>>8>0xffffffff or owner['constant_buffer_valid_mask']!=6 or math.prod(owner['groups_shape'])*math.prod(owner['local_shape'])>128:raise ValueError('Resident geometry/address differs')
    stream+=struct.pack('<6I',0x200120ad,addr>>8,0x200120af,3,0x20012044,0)
   if hashlib.sha256(stream).hexdigest()!=proof['stream_SHA256']:raise ValueError('Resident stream hash differs')
  items.append((p,v,i,m))
 for p,form in zip(paths[9:11],('groups','threads')):
  v=verify_uniform(p);i=read(p/'inputs.json');m=read(p/'execution/manifest.json')
  if v!=read(p/'verification.stdout') or read(p/'verification-execution.json')['exit_code']!=0 or v['form']!=form or v['mode']!='execute':raise ValueError('Uniform regression differs')
  subprocess.run(['codesign','--verify','--strict',str(p/'execution/application')],check=True,capture_output=True,timeout=15);regressions.append((p,v,i,m))
 repeats=[]
 for p,case in zip(paths[14:18],(0,0,6,6)):
  v=verify(p);i=read(p/'inputs.json');m=read(p/'execution/manifest.json')
  if v!=read(p/'verification.stdout') or read(p/'verification-execution.json')['exit_code']!=0 or v['mode']!='execute' or v['case']!=case or v['rows']!=items[case+1][1]['rows']:raise ValueError('Repeat result differs')
  subprocess.run(['codesign','--verify','--strict',str(p/'execution/application')],check=True,capture_output=True,timeout=15)
  for row in read(p/'results.json')['runs']:
   if row['trial']==0:continue
   proof=row['proof'];owners=proof['owner_original_profiles'];addrs=proof['descriptor_GPU_addresses'];stream=bytearray()
   if len(owners)!=v['regions'] or len({x['registration_id'] for x in owners})!=1:raise ValueError('Repeat owner registration differs')
   for owner,addr in zip(owners,addrs):
    if owner['descriptor_GPU_address']!=addr or addr%256 or addr>>8>0xffffffff or owner['constant_buffer_valid_mask']!=6 or math.prod(owner['groups_shape'])*math.prod(owner['local_shape'])>128:raise ValueError('Repeat resident geometry/address differs')
    stream+=struct.pack('<6I',0x200120ad,addr>>8,0x200120af,3,0x20012044,0)
   if hashlib.sha256(stream).hexdigest()!=proof['stream_SHA256']:raise ValueError('Repeat resident stream differs')
  repeats.append((p,v,i,m))
 cohort=items+regressions+repeats
 if len({x[3]['pid'] for x in cohort})!=15 or len({x[2]['runtime_archive_SHA256'] for x in cohort})!=1 or len({x[2]['registry_id'] for x in cohort})!=1 or any(x[2]['profile']!=cohort[0][2]['profile'] for x in cohort):raise ValueError('Runtime/process/device/profile differs')
 ordered=sorted(cohort,key=lambda x:x[3]['started_at'])
 for a,b in zip(ordered,ordered[1:]):
  if datetime.datetime.fromisoformat(a[3]['completed_at'])>=datetime.datetime.fromisoformat(b[3]['started_at']):raise ValueError('GPU hosts overlap')
 if len({x[2]['build_inputs_SHA256'] for x in items+repeats})!=1:raise ValueError('Partial builds differ')
 def comparable(v):return {k:h for k,h in v['raw_SHA256'].items() if not k.endswith('.commands.bin')}
 if len(comparable(regressions[0][1]))!=180 or comparable(regressions[0][1])!=comparable(regressions[1][1]):raise ValueError('Uniform group/thread outputs differ')
 fixed=paths[11];one=paths[12];m1=paths[13];fv=verify_fixed(fixed);ov=verify_1d(one);refs=[verify_m1(m1,True,c) for c in ('qualified-01','qualified-02')]
 if fv['mode']!='execute' or ov['mode']!='execute':raise ValueError('Earlier prototype references absent')
 matches=0
 for p,reference,prefix in [(items[1][0],fixed,'trial-1.post'),(repeats[0][0],fixed,'trial-1.post'),(repeats[1][0],fixed,'trial-1.post'),(items[2][0],one,'trial-3')]:
  for trial in range(1,5):
   for key in ('coordinates','geometry'):
    if (p/'outputs'/f'trial-{trial}.post.{key}.bin').read_bytes()!=(reference/'outputs'/f'{prefix}.{key}.bin').read_bytes():raise ValueError('New and prior GPU result differ')
    matches+=1
 checked=0
 for p in (items[1][0],repeats[0][0],repeats[1][0]):
  for trial in range(1,5):
   c=(p/'outputs'/f'trial-{trial}.post.coordinates.bin').read_bytes();g=(p/'outputs'/f'trial-{trial}.post.geometry.bin').read_bytes()
   for cohort_name in ('qualified-01','qualified-02'):
    raw=(m1/cohort_name/'partial3d/output.bin').read_bytes()
    for index in range(385):
     a=struct.unpack_from('<4I',c,64+index*16)+struct.unpack_from('<4I',g,64+index*16);b=struct.unpack_from('<32I',raw,64+index*128)
     for k,offset in enumerate((0,4,8,12,16,20,24)):
      if a[k]!=pack(b[offset:offset+3]):raise ValueError('New GPU and M1 metadata differ')
      checked+=3
 if checked!=194040 or matches!=32:raise ValueError('Reference comparison count differs')
 return {'audit':'PASS','partial_hosts':13,'partial_execution_hosts':12,'repeat_cases':[0,0,6,6],'uniform_regression_hosts':2,'cases':[{'grid':v['grid'],'local':v['local'],'regions':v['regions'],'threads':v['threads']} for p,v,i,m in items[1:]],
  'partial_user_command_buffers':sum(x[1]['user_command_buffers'] for x in items+repeats),'partial_invocations':sum(x[1]['threads'] for x in items+repeats),'partial_uint32_values':sum(x[1]['uint32_values_checked'] for x in items+repeats),
  'negative_refusal_observations':sum(x[1]['negative_cases'] for x in items+repeats),'uniform_invocations':sum(x[1]['GPU_invocations_counted'] for x in regressions),'uniform_uint32_values':sum(x[1]['correct_uint32_words'] for x in regressions),
  'uniform_paired_data_files':len(comparable(regressions[0][1])),'earlier_gpu_raw_file_matches':matches,'m1_metadata_component_matches':checked,
  'm1_reference_manifest_SHA256':[x['manifest_SHA256'] for x in refs],'fixed_3d_manifest_SHA256':sha(fixed/'execution/manifest.json'),'manual_1d_manifest_SHA256':sha(one/'execution/manifest.json'),
  'runtime_archive_SHA256':items[0][2]['runtime_archive_SHA256'],'core_source_SHA256':items[0][2]['frozen']['src/KeplerCPUICB.mm'],'planner_SHA256':items[0][2]['frozen']['src/KeplerPartialGridPlan.h'],
  'host_source_SHA256':items[0][2]['frozen']['src/partial_general_api_probe.mm'],'driver_file_SHA256':items[0][2]['profile']['system_files_SHA256']['/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver'],
  'partial_manifest_SHA256':[sha(x[0]/'execution/manifest.json') for x in items+repeats],'uniform_manifest_SHA256':[sha(x[0]/'execution/manifest.json') for x in regressions],
  'scope':'Explicit opt-in; exact shader/resources; bounded 3D geometry; serial process-local project ICB','native_apple_ICB':False,'transparent_integration':False,'system_modified':False}
if __name__=='__main__':print(json.dumps(audit(sys.argv[1:]),indent=2,sort_keys=True))
