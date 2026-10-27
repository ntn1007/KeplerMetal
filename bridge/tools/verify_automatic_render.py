#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent image, provenance, scope and restoration checks."""
from pathlib import Path
import math,struct
from public_large_scratch import read,sha
from verify_local_memory import verify_device_identity
MODES=('auto','auto_multiple','direct','no_auto','unsupported','manual','auto_direct','guard_restore')
def verify(path):
 path=Path(path);inp=read(path/'inputs.json');d=read(path/'results.json');r=read(path/'execution/manifest.json');mode=d['mode'];assert mode in MODES and inp['mode']==mode and d==read(path/'execution/execution.stdout');verify_device_identity(d)
 lease=r['GPU_reservation'];assert r['exit_code']==0 and not r['SIGKILL_requested'] and not r['authoritative_ps_status'] and lease['state']=='terminal' and lease['exit_code']==0 and lease['child_PID']==r['pid'] and not lease['known_signed_processes_live']
 assert sha(path/'application')==inp['executable_SHA256']==r['original_binary_sha256'] and sha(path/'execution/application')==r['signed_binary_sha256']==lease['signed_binary_sha256']
 for name,digest in inp['frozen'].items():assert sha(path/name)==digest,name
 assert r['launcher_SHA256']==inp['frozen']['runtime/run_sdk_host.py'] and r['reservation_module_SHA256']==inp['frozen']['runtime/lab_gpu_reservation.py'] and r['arguments']==[str(path/'assets'),str(path/'assets/client.dylib'),str(path/'outputs'),mode]
 assert d['status']=='PASS' and d['device_and_queue_restored'] and not d['shared_native_classes_replaced'] and d['shared_native_methods_checked']==3 and d['other_queue_untouched'] and not d['unmodified_existing_app'] and not d['performance_benchmark'] and not d['post_restore_buffer_class'].startswith('KPAutomatic')
 assert d['synthetic_compute_ICB_guard_refused']==(mode=='guard_restore')
 assert d['restored_enable_refused']==(mode!='direct') and d['live_restoration_checked']==(mode in ('manual','guard_restore')) and d['live_restoration_passed']
 c=d['client'];events=d['scope_events'];find=lambda n:[e for e in events if e['operation']==n];count=3 if mode=='auto_multiple' else 1;w,h=(32,32) if mode=='unsupported' else (64,48)
 expected_exception={'name':'KeplerCPUICBUnsupported','reason':'Project render ICB cannot execute on an unqualified native render pass'}
 assert c['unsupported_exceptions']==([expected_exception,expected_exception] if mode=='unsupported' else [])
 assert c['unsupported_ICB_refused']==(mode=='unsupported') and c['unsupported_indirect_refused']==(mode=='unsupported')
 assert c['status']=='PASS' and c['frames']==count and (c['width'],c['height'])==(w,h) and c['command_status']==4
 assert c['did_execute_icb']==(mode in ('auto','auto_multiple','manual','guard_restore')) and c['used_standard_direct_draw']==(mode in ('direct','unsupported','auto_direct'))
 assert not c['compute_encoder_class'].startswith('KP')
 if mode in ('auto','auto_multiple','manual','auto_direct','guard_restore'):
  assert c['command_buffer_class'].startswith('KPAutomaticCommandBuffer_') and all(x.startswith('KPICBRenderEncoder_') for x in c['render_encoder_classes'])
  assert len(find('automatic_render_factories_enabled'))==1 and len(find('automatic_render_encoder'))>=count+(1 if mode=='manual' else 0)
  assert len(find('execute_CPU_render_ICB'))==(0 if mode=='auto_direct' else count) and all(e['executed_indices']==[0] for e in find('execute_CPU_render_ICB'))
 elif mode=='unsupported':
  assert c['command_buffer_class'].startswith('KPAutomaticCommandBuffer_') and all(x.startswith('KPGuardedRenderEncoder_') for x in c['render_encoder_classes']) and len(find('automatic_render_passthrough'))==1 and find('automatic_render_passthrough')[0]['project_ICB_guarded'] and not find('automatic_render_encoder')
 else:assert not c['command_buffer_class'].startswith('KP') and all(not x.startswith('KP') for x in c['render_encoder_classes']) and not find('automatic_render_encoder')
 if mode not in ('direct','no_auto'):assert len(find('automatic_render_factories_restored'))==1 and find('automatic_render_factories_restored')[0]['queue_class_restored']
 if mode=='guard_restore':assert len(find('automatic_render_passthrough'))==1 and find('automatic_render_passthrough')[0]['project_ICB_guarded']
 if mode=='no_auto':assert not find('automatic_render_factories_enabled') and not find('execute_CPU_render_ICB')
 desired=(0.,0.,0.,0.) if mode=='no_auto' else (.75,.125,.25,1.)
 checked=0
 for i in range(count):
  b=(path/f'outputs/frame-{i}.bin').read_bytes();assert len(b)==w*h*16+512 and b[:256]==b[-256:]==b'\xa5'*256
  values=struct.unpack('<%df'%(w*h*4),b[256:-256]);assert all(math.isfinite(value) and value==desired[j%4] for j,value in enumerate(values));checked+=len(values)
 return {'status':'PASS','mode':mode,'frames':count,'checked_float_channels':checked,'scope_automatic_render':mode not in ('direct','no_auto','unsupported'),'ICB_executed':c['did_execute_icb'],'unsupported_pass_guarded_native_draw':mode=='unsupported','unmodified_existing_app':False,'performance_benchmark':False}
