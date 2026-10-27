#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify four serialized edge-builtins cohort hosts and their retained raw evidence."""
import datetime,hashlib,json,struct,subprocess,sys
from pathlib import Path
from verify_partial_nominal import verify,read,sha,GROUPS,LOCAL

def audit(paths):
 if len(paths)!=4:raise ValueError('One preparation and three execution hosts required')
 paths=[Path(p).resolve() for p in paths];values=[];manifests=[];inputs=[]
 for index,p in enumerate(paths):
  v=verify(p);m=read(p/'execution/manifest.json');i=read(p/'inputs.json')
  if v!=read(p/'verification.stdout') or read(p/'verification-execution.json')!={'exit_code':0,'isolated_interpreter':True} or v['mode']!=('prepare' if index==0 else 'execute'):raise ValueError('Host qualification differs')
  subprocess.run(['codesign','--verify','--strict',str(p/'execution/application')],check=True,capture_output=True,timeout=15)
  output=p/'outputs';host=read(p/'results.json')
  for node in range(3):
   c=(output/f'baseline-{node}.constants.bin').read_bytes();q=(output/f'baseline-{node}.qmd.bin').read_bytes();g,l=GROUPS[node],LOCAL[node]
   builtin=struct.unpack_from('<24I',c,0x6f0)
   expected=(*l,0,*g,0,0,0,0,0,*(a*b for a,b in zip(g,l)),0,*l,0,*g,0)
   if builtin!=expected:raise ValueError('Native initial builtin geometry differs')
   word=lambda n:struct.unpack_from('<I',q,n)[0]
   if word(0x30)!=g[0] or word(0x34)!=g[1]|g[2]<<16 or word(0x48)>>16!=l[0] or word(0x4c)!=l[1]|l[2]<<16 or word(0x50)&255!=6 or word(0xb8)>>24!=21:raise ValueError('Resident QMD geometry/profile differs')
  for row in host['runs']:
   proof=row['proof'];node=row['node'];addr=proof['descriptor_GPU_address'];suppressed=row['suppressed'];owner=proof['owner_original_profiles'][0]
   if addr%256 or addr>>8>0xffffffff or owner['descriptor_GPU_address']!=addr or owner['groups_shape']!=list(GROUPS[node]) or owner['local_shape']!=list(LOCAL[node]) or owner['original_record_function']!='grid_coordinates' or owner['constant_buffer_valid_mask']!=6 or owner['native_register_count']!=21:raise ValueError('Resident owner profile differs')
   stream=struct.pack('<6I',0x200120ad,addr>>8,0x20012040 if suppressed else 0x200120af,0 if suppressed else 3,0x20012044,0)
   if hashlib.sha256(stream).hexdigest()!=proof['stream_SHA256']:raise ValueError('Resident launch select/launch/wait stream hash differs')
  values.append(v);manifests.append(m);inputs.append(i)
 if len({m['pid'] for m in manifests})!=4 or len({i['build_inputs_SHA256'] for i in inputs})!=1 or len({i['registry_id'] for i in inputs})!=1 or any(i['profile']!=inputs[0]['profile'] for i in inputs):raise ValueError('Process, build, device or profile identity differs')
 for a,b in zip(manifests,manifests[1:]):
  if datetime.datetime.fromisoformat(a['completed_at'])>=datetime.datetime.fromisoformat(b['started_at']):raise ValueError('Hosts overlap or are out of order')
 if any(v['rows']!=values[1]['rows'] for v in values[2:]):raise ValueError('Raw output hashes differ across independent hosts')
 return {'audit':'PASS','processes':4,'preparation_processes':1,'execution_processes':3,'same_frozen_build':True,
  'user_dispatches':sum(v['user_dispatches'] for v in values),'threads':sum(v['threads'] for v in values),
  'uint32_values_checked':sum(v['uint32_values_checked'] for v in values),'suppressed_controls':sum(v['suppressed_controls'] for v in values),
  'coordinate_geometry_output_hashes_repeat':True,'qmd_and_builtin_geometry_checked':True,'reported_resident_stream_hashes_checked':True,'frozen_host_SHA256':inputs[0]['executable_SHA256'],
  'runtime_archive_SHA256':inputs[0]['runtime_archive_SHA256'],'native_library_SHA256':inputs[0]['library_SHA256'],
  'source_SHA256':inputs[0]['frozen']['src/partial_nominal_probe.mm'],
  'execution_manifest_SHA256':[sha(p/'execution/manifest.json') for p in paths],
  'driver_file_SHA256':inputs[0]['profile']['system_files_SHA256']['/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver'],
  'partial_threadgroups_implemented':False,'system_modified':False,'transparent_integration':False}
if __name__=='__main__':print(json.dumps(audit(sys.argv[1:]),indent=2,sort_keys=True))
