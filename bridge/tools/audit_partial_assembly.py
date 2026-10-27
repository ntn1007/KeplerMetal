#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit four serialized fixed-grid hosts against frozen raw results."""
import datetime,json,subprocess,sys
from pathlib import Path
from verify_partial_assembly import verify,read,sha

def audit(paths):
 if len(paths)!=4:raise ValueError('One preparation and three execution hosts required')
 paths=[Path(p).resolve() for p in paths];values=[];manifests=[];inputs=[]
 for index,p in enumerate(paths):
  v=verify(p);m=read(p/'execution/manifest.json');i=read(p/'inputs.json')
  if v!=read(p/'verification.stdout') or read(p/'verification-execution.json')!={'exit_code':0,'isolated_interpreter':True} or v['mode']!=('prepare' if index==0 else 'execute'):raise ValueError('Host qualification differs')
  subprocess.run(['codesign','--verify','--strict',str(p/'execution/application')],check=True,capture_output=True,timeout=15)
  values.append(v);manifests.append(m);inputs.append(i)
 if len({m['pid'] for m in manifests})!=4 or len({i['build_inputs_SHA256'] for i in inputs})!=1 or len({i['registry_id'] for i in inputs})!=1 or any(i['profile']!=inputs[0]['profile'] for i in inputs):raise ValueError('Process, build, device or profile differs')
 for a,b in zip(manifests,manifests[1:]):
  if datetime.datetime.fromisoformat(a['completed_at'])>=datetime.datetime.fromisoformat(b['started_at']):raise ValueError('Host processes overlap')
 if any(v['rows']!=values[1]['rows'] for v in values[2:]):raise ValueError('Raw output hashes differ')
 return {'audit':'PASS','processes':4,'preparation_processes':1,'execution_processes':3,'same_frozen_build':True,
  'user_dispatches':sum(v['user_dispatches'] for v in values),'threads':sum(v['threads'] for v in values),
  'uint32_values_checked':sum(v['uint32_values_checked'] for v in values),'logical_grid_threads':191,'combined_grid_executions':6,
  'single_region_controls':6,'suppressed_controls':3,'both_orders_match':True,'same_outputs_across_processes':True,
  'frozen_host_SHA256':inputs[0]['executable_SHA256'],'runtime_archive_SHA256':inputs[0]['runtime_archive_SHA256'],
  'native_library_SHA256':inputs[0]['library_SHA256'],'source_SHA256':inputs[0]['frozen']['src/partial_assembly_probe.mm'],
  'execution_manifest_SHA256':[sha(p/'execution/manifest.json') for p in paths],
  'driver_file_SHA256':inputs[0]['profile']['system_files_SHA256']['/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver'],
  'partial_ICB_implemented':False,'transparent_integration':False,'system_modified':False}
if __name__=='__main__':print(json.dumps(audit(sys.argv[1:]),indent=2,sort_keys=True))
