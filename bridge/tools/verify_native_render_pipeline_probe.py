#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify signed construction-only observations without inferring execution."""
from pathlib import Path
from public_large_scratch import read,sha
from verify_local_memory import verify_device_identity


def verify(path):
 path=Path(path);inputs=read(path/'inputs.json');d=read(path/'results.json');receipt=read(path/'execution/manifest.json');verify_device_identity(d);assert d==read(path/'execution/execution.stdout')
 lease=receipt['GPU_reservation'];assert receipt['exit_code']==0 and not receipt['SIGKILL_requested'] and not receipt['authoritative_ps_status'] and lease['state']=='terminal' and lease['exit_code']==0 and lease['child_PID']==receipt['pid'] and not lease['known_signed_processes_live']
 assert sha(path/'application')==inputs['executable_SHA256']==receipt['original_binary_sha256'];assert sha(path/'execution/application')==receipt['signed_binary_sha256']==lease['signed_binary_sha256']
 for name,digest in inputs['frozen'].items():assert sha(path/name)==digest,name
 assert receipt['launcher_SHA256']==inputs['frozen']['runtime/run_sdk_host.py'] and receipt['reservation_module_SHA256']==inputs['frozen']['runtime/lab_gpu_reservation.py']
 assert receipt['arguments']==[str(path/'assets/graphics.metallib'),str(path/'assets/probe.metallib')]
 assert d['GPU_command_buffers']==d['GPU_dispatches']==0 and d['interposition'] is False
 assert len(d['render_pipelines'])==2 and [x['support_icb_requested']for x in d['render_pipelines']]==[False,True] and d['render_pipelines'][0]['created'] is True
 for row in d['render_pipelines']:
  if row.get('id_returned'):assert type(row['id_word'])is int
 arg=d['render_argument_descriptor'];assert isinstance(arg,dict) and ('created'in arg or 'exception'in arg)
 if arg.get('length',0)>0 and 'encoded_word'in arg:assert arg['guards_intact'] is True
 assert isinstance(d['typed_function_encoder'],dict) and isinstance(d['typed_compute_pipeline'],dict)
 return {'status':'PASS_NATIVE_OBSERVATION','GPU_dispatches':0,'render_pipelines':d['render_pipelines'],'render_argument_descriptor':arg,'typed_function_encoder':d['typed_function_encoder'],'typed_compute_pipeline':d['typed_compute_pipeline']}
