#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit fixed-profile ICB integration, uniform regressions and references."""
import datetime,hashlib,json,struct,subprocess,sys
from pathlib import Path
from verify_partial_icb_api import verify,read,sha
from verify_uniform_icb_3d import verify as verify_uniform
from verify_partial_assembly_3d import verify as verify_proto,pack
from verify_partial_grid_m1 import verify as verify_m1

def audit(paths):
 if len(paths)!=8:raise ValueError('Preparation, three ICB hosts, two uniform hosts, prototype and M1 root required')
 paths=[Path(p).resolve() for p in paths];items=[];regressions=[]
 for index,p in enumerate(paths[:4]):
  v=verify(p);i=read(p/'inputs.json');m=read(p/'execution/manifest.json');d=read(p/'results.json')
  if v!=read(p/'verification.stdout') or read(p/'verification-execution.json')!={'exit_code':0,'isolated_interpreter':True} or v['mode']!=('prepare' if index==0 else 'execute'):raise ValueError('Partial host qualification differs')
  subprocess.run(['codesign','--verify','--strict',str(p/'execution/application')],check=True,capture_output=True,timeout=15)
  for row in d['runs']:
   if row['trial']==0:continue
   proof=row['proof'];stream=bytearray();owners=proof['owner_original_profiles'];addrs=proof['descriptor_GPU_addresses']
   if len(owners)!=8 or len({x['registration_id'] for x in owners})!=1:raise ValueError('Partial owner registration differs')
   for n,(owner,addr) in enumerate(zip(owners,addrs)):
    group=[1 if n&4 else 2,1,1];local=[3 if n&4 else 4,3 if n&2 else 4,2 if n&1 else 3]
    if owner['groups_shape']!=group or owner['local_shape']!=local or owner['descriptor_GPU_address']!=addr or addr%256 or addr>>8>0xffffffff or owner['constant_buffer_valid_mask']!=6:raise ValueError('Partial resident geometry or address differs')
    stream+=struct.pack('<6I',0x200120ad,addr>>8,0x200120af,3,0x20012044,0)
   if hashlib.sha256(stream).hexdigest()!=proof['stream_SHA256']:raise ValueError('Partial resident stream hash differs')
  items.append((p,v,i,m))
 for p,form in zip(paths[4:6],('groups','threads')):
  v=verify_uniform(p);i=read(p/'inputs.json');m=read(p/'execution/manifest.json')
  if v!=read(p/'verification.stdout') or read(p/'verification-execution.json')['exit_code']!=0 or v['form']!=form or v['mode']!='execute':raise ValueError('Uniform regression differs')
  subprocess.run(['codesign','--verify','--strict',str(p/'execution/application')],check=True,capture_output=True,timeout=15);regressions.append((p,v,i,m))
 cohort=items+regressions
 if len({x[3]['pid'] for x in cohort})!=6 or len({x[2]['runtime_archive_SHA256'] for x in cohort})!=1 or len({x[2]['registry_id'] for x in cohort})!=1 or any(x[2]['profile']!=cohort[0][2]['profile'] for x in cohort):raise ValueError('Runtime, process, device or profile differs')
 ordered=sorted(cohort,key=lambda x:x[3]['started_at'])
 for a,b in zip(ordered,ordered[1:]):
  if datetime.datetime.fromisoformat(a[3]['completed_at'])>=datetime.datetime.fromisoformat(b[3]['started_at']):raise ValueError('GPU hosts overlap')
 if len({x[2]['build_inputs_SHA256'] for x in items})!=1 or any(x[1]['rows']!=items[1][1]['rows'] for x in items[2:]):raise ValueError('Partial builds or outputs differ')
 def comparable(v):return {k:h for k,h in v['raw_SHA256'].items() if not k.endswith('.commands.bin')}
 if len(comparable(regressions[0][1]))!=180 or comparable(regressions[0][1])!=comparable(regressions[1][1]):raise ValueError('Uniform group/thread outputs differ')
 proto=paths[6];pv=verify_proto(proto)
 if pv['mode']!='execute':raise ValueError('Prototype reference missing')
 m1=paths[7];refs=[verify_m1(m1,True,c) for c in ('qualified-01','qualified-02')];checked=raw_matches=0
 for p,v,i,m in items[1:]:
  for trial in range(1,5):
   c=(p/'outputs'/f'trial-{trial}.post.coordinates.bin').read_bytes();g=(p/'outputs'/f'trial-{trial}.post.geometry.bin').read_bytes()
   if c!=(proto/'outputs/trial-9.coordinates.bin').read_bytes() or g!=(proto/'outputs/trial-9.geometry.bin').read_bytes():raise ValueError('ICB and manual prototype differ')
   raw_matches+=2
   for cohort_name in ('qualified-01','qualified-02'):
    raw=(m1/cohort_name/'partial3d/output.bin').read_bytes()
    for index in range(385):
     a=struct.unpack_from('<4I',c,64+index*16)+struct.unpack_from('<4I',g,64+index*16);b=struct.unpack_from('<32I',raw,64+index*128)
     for k,offset in enumerate((0,4,8,12,16,20,24)):
      if a[k]!=pack(b[offset:offset+3]):raise ValueError('ICB and M1 metadata differ')
      checked+=3
 if checked!=194040 or raw_matches!=24:raise ValueError('Reference comparison count differs')
 return {'audit':'PASS','partial_hosts':4,'partial_execution_hosts':3,'uniform_regression_hosts':2,
  'partial_user_command_buffers':sum(x[1]['user_command_buffers'] for x in items),'partial_invocations':sum(x[1]['threads'] for x in items),'partial_uint32_values':sum(x[1]['uint32_values_checked'] for x in items),
  'negative_refusal_observations':sum(x[1]['negative_cases'] for x in items),'uniform_invocations':sum(x[1]['GPU_invocations_counted'] for x in regressions),'uniform_uint32_values':sum(x[1]['correct_uint32_words'] for x in regressions),
  'uniform_paired_data_files':len(comparable(regressions[0][1])),'prototype_raw_file_matches':raw_matches,'m1_metadata_component_matches':checked,
  'm1_reference_manifest_SHA256':[x['manifest_SHA256'] for x in refs], 'manual_prototype_manifest_SHA256':sha(proto/'execution/manifest.json'),
  'runtime_archive_SHA256':items[0][2]['runtime_archive_SHA256'],'core_source_SHA256':items[0][2]['frozen']['src/KeplerCPUICB.mm'],
  'host_source_SHA256':items[0][2]['frozen']['src/partial_icb_api_probe.mm'],'driver_file_SHA256':items[0][2]['profile']['system_files_SHA256']['/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver'],
  'partial_manifest_SHA256':[sha(x[0]/'execution/manifest.json') for x in items], 'uniform_manifest_SHA256':[sha(x[0]/'execution/manifest.json') for x in regressions],
  'scope':'Explicit opt-in, exact shader/grid/resources; serial process-local project ICB','native_apple_ICB':False,'transparent_integration':False,'system_modified':False}
if __name__=='__main__':print(json.dumps(audit(sys.argv[1:]),indent=2,sort_keys=True))
