#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify a pipeline inspection and four serialized edge-builtins cohort hosts and their retained raw evidence."""
import datetime,hashlib,json,struct,subprocess,sys
from pathlib import Path
from verify_partial_builtin import verify,read,sha,GROUPS,LOCAL

def audit(paths):
 if len(paths)!=5:raise ValueError('Pipeline inspection, preparation and three execution hosts required')
 inspection=Path(paths[0]).resolve();paths=[Path(p).resolve() for p in paths[1:]];values=[];manifests=[];inputs=[]
 ci=read(inspection/'inputs.json');cm=read(inspection/'execution/manifest.json');d=read(inspection/'results.json');lease=cm['GPU_reservation']
 if d!=read(inspection/'execution/execution.stdout') or d['GPU_dispatch'] or d['committed'] or cm['exit_code']!=0 or cm['SIGKILL_requested'] or cm['authoritative_ps_status'] or lease['state']!='terminal' or lease['child_PID']!=cm['pid'] or lease['known_signed_processes_live']:raise ValueError('Pipeline inspection was submitted or failed')
 if len(d['records'])!=1 or d['records'][0]['function']!='partial_builtin_barrier' or d['records'][0]['static_threadgroup_bytes']!=256 or not d['records'][0]['reflection_available']:raise ValueError('Pipeline reflection differs')
 for name,digest in ci['frozen'].items():
  if sha(inspection/name)!=digest:raise ValueError('Pipeline frozen input changed')
 if sha(inspection/'application')!=ci['executable_SHA256'] or sha(inspection/'execution/application')!=cm['signed_binary_sha256'] or sha(inspection/'assets/shader.metallib')!=d['library_SHA256'] or sha(inspection/'capture/partial_builtin_barrier.commands.bin')!=d['records'][0]['command_SHA256']:raise ValueError('Pipeline host or source artifacts differ')
 subprocess.run(['codesign','--verify','--strict',str(inspection/'execution/application')],check=True,capture_output=True,timeout=15)
 repo=Path(__file__).resolve().parents[1]
 if sha(repo/'src/partial_builtin_barrier.metal')!=ci['frozen']['src/partial_builtin_barrier.metal']:raise ValueError('Current shader source differs from compiled source')
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
   if word(0x30)!=g[0] or word(0x34)!=g[1]|g[2]<<16 or word(0x48)>>16!=l[0] or word(0x4c)!=l[1]|l[2]<<16 or word(0x50)&255!=6 or word(0xb8)>>24!=22 or word(0x44)&0x3ffff!=256:raise ValueError('Resident QMD geometry/profile differs')
  for row in host['runs']:
   proof=row['proof'];node=row['node'];addr=proof['descriptor_GPU_address'];suppressed=row['suppressed'];owner=proof['owner_original_profiles'][0]
   if addr%256 or addr>>8>0xffffffff or owner['descriptor_GPU_address']!=addr or owner['groups_shape']!=list(GROUPS[node]) or owner['local_shape']!=list(LOCAL[node]) or owner['original_record_function']!='partial_builtin_barrier' or owner['constant_buffer_valid_mask']!=6 or owner['native_register_count']!=22:raise ValueError('Resident owner profile differs')
   stream=struct.pack('<6I',0x200120ad,addr>>8,0x20012040 if suppressed else 0x200120af,0 if suppressed else 3,0x20012044,0)
   if hashlib.sha256(stream).hexdigest()!=proof['stream_SHA256']:raise ValueError('Resident launch select/launch/wait stream hash differs')
  values.append(v);manifests.append(m);inputs.append(i)
 if len({m['pid'] for m in manifests})!=4 or len({i['build_inputs_SHA256'] for i in inputs})!=1 or len({i['registry_id'] for i in inputs})!=1 or any(i['profile']!=inputs[0]['profile'] for i in inputs):raise ValueError('Process, build, device or profile identity differs')
 for a,b in zip(manifests,manifests[1:]):
  if datetime.datetime.fromisoformat(a['completed_at'])>=datetime.datetime.fromisoformat(b['started_at']):raise ValueError('Hosts overlap or are out of order')
 if any(v['rows']!=values[1]['rows'] for v in values[2:]):raise ValueError('Raw output hashes differ across independent hosts')
 if ci['profile']!=inputs[0]['profile'] or ci['registry_id']!=inputs[0]['registry_id'] or d['library_SHA256']!=inputs[0]['library_SHA256'] or cm['pid'] in {m['pid'] for m in manifests} or datetime.datetime.fromisoformat(cm['completed_at'])>=datetime.datetime.fromisoformat(manifests[0]['started_at']):raise ValueError('Pipeline and execution provenance differ')
 return {'audit':'PASS','processes':5,'pipeline_inspection_processes':1,'preparation_processes':1,'execution_processes':3,'same_frozen_build':True,
  'user_dispatches':sum(v['user_dispatches'] for v in values),'threads':sum(v['threads'] for v in values),
  'uint32_values_checked':sum(v['uint32_values_checked'] for v in values),'suppressed_controls':sum(v['suppressed_controls'] for v in values),
  'coordinate_geometry_output_hashes_repeat':True,'qmd_and_builtin_geometry_checked':True,'static_threadgroup_bytes':256,'shader_witnesses_checked':True,'reported_resident_stream_hashes_checked':True,'frozen_host_SHA256':inputs[0]['executable_SHA256'],
  'runtime_archive_SHA256':inputs[0]['runtime_archive_SHA256'],'native_library_SHA256':inputs[0]['library_SHA256'],
  'source_SHA256':inputs[0]['frozen']['src/partial_builtin_run_probe.mm'],'shader_source_SHA256':ci['frozen']['src/partial_builtin_barrier.metal'],'shader_air_SHA256':ci['frozen']['assets/shader.air'],'pipeline_manifest_SHA256':sha(inspection/'execution/manifest.json'),
  'execution_manifest_SHA256':[sha(p/'execution/manifest.json') for p in paths],
  'driver_file_SHA256':inputs[0]['profile']['system_files_SHA256']['/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver'],
  'partial_threadgroups_implemented':False,'system_modified':False,'transparent_integration':False}
if __name__=='__main__':print(json.dumps(audit(sys.argv[1:]),indent=2,sort_keys=True))
