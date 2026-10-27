#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit extra Y/Z tiled cases on the same bounded ICB runtime."""
import datetime,hashlib,json,math,struct,subprocess,sys
from pathlib import Path
from verify_partial_general_extra import verify,read,sha
from verify_uniform_icb_3d import verify as verify_uniform

def audit(paths):
 if len(paths)!=5:raise ValueError('Four extra cases and the preceding uniform regression required')
 paths=[Path(p).resolve() for p in paths];reference=paths[-1];refi=read(reference/'inputs.json');refm=read(reference/'execution/manifest.json');rv=verify_uniform(reference);items=[]
 if rv['mode']!='execute' or rv['form']!='threads' or rv!=read(reference/'verification.stdout'):raise ValueError('Preceding uniform reference differs')
 for case,p in enumerate(paths[:4]):
  v=verify(p);i=read(p/'inputs.json');m=read(p/'execution/manifest.json');d=read(p/'results.json')
  if v!=read(p/'verification.stdout') or read(p/'verification-execution.json')['exit_code']!=0 or v['mode']!='execute' or v['case']!=case:raise ValueError('Extra host qualification differs')
  subprocess.run(['codesign','--verify','--strict',str(p/'execution/application')],check=True,capture_output=True,timeout=15)
  for row in d['runs']:
   if not row['trial']:continue
   proof=row['proof'];owners=proof['owner_original_profiles'];addrs=proof['descriptor_GPU_addresses'];stream=bytearray()
   if len(owners)!=v['regions'] or len({x['registration_id'] for x in owners})!=1:raise ValueError('Extra owner registration differs')
   for owner,addr in zip(owners,addrs):
    if owner['descriptor_GPU_address']!=addr or addr%256 or addr>>8>0xffffffff or owner['constant_buffer_valid_mask']!=6 or math.prod(owner['groups_shape'])*math.prod(owner['local_shape'])>128:raise ValueError('Extra resident geometry/address differs')
    stream+=struct.pack('<6I',0x200120ad,addr>>8,0x200120af,3,0x20012044,0)
   if hashlib.sha256(stream).hexdigest()!=proof['stream_SHA256']:raise ValueError('Extra resident stream differs')
  items.append((p,v,i,m))
 if len({x[3]['pid'] for x in items}|{refm['pid']})!=5 or len({x[2]['build_inputs_SHA256'] for x in items})!=1 or any(x[2]['runtime_archive_SHA256']!=refi['runtime_archive_SHA256'] or x[2]['registry_id']!=refi['registry_id'] or x[2]['profile']!=refi['profile'] for x in items):raise ValueError('Extra build, runtime, device or process differs')
 ordered=[(None,None,refi,refm)]+items
 for a,b in zip(ordered,ordered[1:]):
  if datetime.datetime.fromisoformat(a[3]['completed_at'])>=datetime.datetime.fromisoformat(b[3]['started_at']):raise ValueError('Extra hosts overlap or are out of order')
 return {'audit':'PASS','extra_execution_hosts':4,'cases':[{'grid':v['grid'],'local':v['local'],'regions':v['regions'],'threads':v['threads']} for p,v,i,m in items],
  'user_command_buffers':sum(v['user_command_buffers'] for p,v,i,m in items),'invocations':sum(v['threads'] for p,v,i,m in items),'uint32_values':sum(v['uint32_values_checked'] for p,v,i,m in items),'negative_refusal_observations':sum(v['negative_cases'] for p,v,i,m in items),
  'runtime_archive_SHA256':refi['runtime_archive_SHA256'],'core_source_SHA256':items[0][2]['frozen']['src/KeplerCPUICB.mm'],'planner_SHA256':items[0][2]['frozen']['src/KeplerPartialGridPlan.h'],
  'host_source_SHA256':items[0][2]['frozen']['src/partial_general_extra_probe.mm'],'previous_uniform_manifest_SHA256':sha(reference/'execution/manifest.json'),'execution_manifest_SHA256':[sha(p/'execution/manifest.json') for p,v,i,m in items],
  'scope':'Explicit opt-in exact shader/resources; additional bounded Y/Z/2D/3D shapes','native_apple_ICB':False,'transparent_integration':False,'system_modified':False}
if __name__=='__main__':print(json.dumps(audit(sys.argv[1:]),indent=2,sort_keys=True))
