#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the exact 16-region boundary and the over-limit API refusal."""
import datetime,hashlib,json,math,struct,subprocess,sys
from pathlib import Path
from verify_partial_general_limit import verify,read,sha
from verify_partial_general_extra import verify as verify_extra

def audit(paths):
 if len(paths)!=3:raise ValueError('Preparation, execution and previous extra-axis host required')
 p,e,previous=map(lambda x:Path(x).resolve(),paths);items=[];pv=verify_extra(previous);pi=read(previous/'inputs.json');pm=read(previous/'execution/manifest.json')
 if pv['mode']!='execute' or pv['case']!=3 or pv!=read(previous/'verification.stdout'):raise ValueError('Previous host differs')
 for path,mode in ((p,'prepare'),(e,'execute')):
  v=verify(path);i=read(path/'inputs.json');m=read(path/'execution/manifest.json');d=read(path/'results.json')
  if v!=read(path/'verification.stdout') or read(path/'verification-execution.json')['exit_code']!=0 or v['mode']!=mode or v['regions']!=16:raise ValueError('Boundary host qualification differs')
  subprocess.run(['codesign','--verify','--strict',str(path/'execution/application')],check=True,capture_output=True,timeout=15)
  for row in d['runs']:
   if not row['trial']:continue
   proof=row['proof'];owners=proof['owner_original_profiles'];addrs=proof['descriptor_GPU_addresses'];stream=bytearray()
   if len(owners)!=16 or len({x['registration_id'] for x in owners})!=1:raise ValueError('Boundary owner registration differs')
   for owner,addr in zip(owners,addrs):
    if owner['descriptor_GPU_address']!=addr or addr%256 or addr>>8>0xffffffff or owner['constant_buffer_valid_mask']!=6 or math.prod(owner['groups_shape'])*math.prod(owner['local_shape'])>128:raise ValueError('Boundary resident geometry/address differs')
    stream+=struct.pack('<6I',0x200120ad,addr>>8,0x200120af,3,0x20012044,0)
   if hashlib.sha256(stream).hexdigest()!=proof['stream_SHA256']:raise ValueError('Boundary resident stream differs')
  items.append((path,v,i,m))
 if len({pm['pid'],items[0][3]['pid'],items[1][3]['pid']})!=3 or items[0][2]['build_inputs_SHA256']!=items[1][2]['build_inputs_SHA256'] or any(x[2]['runtime_archive_SHA256']!=pi['runtime_archive_SHA256'] or x[2]['registry_id']!=pi['registry_id'] or x[2]['profile']!=pi['profile'] for x in items):raise ValueError('Boundary build/runtime/device/process differs')
 for a,b in ((pm,items[0][3]),(items[0][3],items[1][3])):
  if datetime.datetime.fromisoformat(a['completed_at'])>=datetime.datetime.fromisoformat(b['started_at']):raise ValueError('Boundary hosts overlap')
 return {'audit':'PASS','preparation_hosts':1,'execution_hosts':1,'grid':[14,23,3],'local':[12,3,2],'regions':16,
  'user_command_buffers':sum(x[1]['user_command_buffers'] for x in items),'invocations':sum(x[1]['threads'] for x in items),'uint32_values':sum(x[1]['uint32_values_checked'] for x in items),'negative_refusal_observations':sum(x[1]['negative_cases'] for x in items),'over_16_regions_refused':True,
  'runtime_archive_SHA256':pi['runtime_archive_SHA256'],'core_source_SHA256':items[0][2]['frozen']['src/KeplerCPUICB.mm'],'planner_SHA256':items[0][2]['frozen']['src/KeplerPartialGridPlan.h'],
  'host_source_SHA256':items[0][2]['frozen']['src/partial_general_limit_probe.mm'],'previous_extra_manifest_SHA256':sha(previous/'execution/manifest.json'),'execution_manifest_SHA256':[sha(x[0]/'execution/manifest.json') for x in items],
  'scope':'Explicit opt-in exact shader/resources; 16 regions and over-limit refusal','native_apple_ICB':False,'transparent_integration':False,'system_modified':False}
if __name__=='__main__':print(json.dumps(audit(sys.argv[1:]),indent=2,sort_keys=True))
