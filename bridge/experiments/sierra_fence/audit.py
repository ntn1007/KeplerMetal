#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit Sierra synthetic data-buffer success and intercepted fence failure path."""
import argparse,hashlib,json,pathlib
B=R=BUILD=GUARD=OLD=None;SHA='bf2110a8a74786fe06da672e35f05a0dbd554aa651a83bacf02753c5899ef567'
CASES=[('video-sierra-fence-final-fence-probe-20261027-01','fence-probe','SYNTHETIC_FENCE_PROBE'),('video-sierra-fence-final-fence-probe-20261027-02','fence-probe','SYNTHETIC_FENCE_PROBE'),('video-sierra-fence-final-inspect-20261027-01','inspect','INSPECT_PASS'),('video-sierra-fence-final-wrong-20261027-01','wrong','WRONG_IMAGE_REFUSED'),('video-sierra-fence-final-null-create-20261027-01','null-create','NULL_CREATE_REJECTED')]
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(pathlib.Path(p).read_text())
def check(v,s):
 if not v:raise ValueError(s)
def audit():
 check(sha(OLD)==SHA,'candidate');b=read(BUILD/'inputs.json');g=read(GUARD/'inputs.json')
 original=(BUILD/'stage-guard.mm').read_bytes();published=(pathlib.Path(__file__).resolve().parent/'stage-guard.mm').read_bytes()
 old=b'// Synthetic tokens and data buffer; fence request is refused locally.'
 new=b'// Synthetic tokens and data buffer; fence success is fabricated and device config is refused locally.'
 check(original.count(old)==1 and original.replace(old,new)==published,'published guard differs beyond corrected comment')
 check(sha(BUILD/'coordinator.py')==sha(pathlib.Path(__file__).resolve().parent/'coordinator.py'),'published coordinator differs')
 for folder,manifest in [(BUILD,b),(GUARD,g)]:
  for p,h in manifest['frozen'].items():check(sha(folder/p)==h,'frozen '+p)
 host=(BUILD/'loader.mm').read_text();stage=(BUILD/'stage-guard.mm').read_text()
 for text in ('uint32_t index=0,mask=1;','allStageSlotsPinned','KPStageCount(6)==1','globalsRestored','providerStatus==11','extraSlots','extraStubs','0xa2128','KPProbeConfigCalibrate','KPProbeConfigCalls()==1'):check(text in host,'host invariant '+text)
 for text in ('return &token;','p!=&token','sharedCount++;return &sharedToken;','p!=&sharedToken','videoCreateCount++;return &videoToken;' ,'releaseCount++;','return kIOReturnNotPermitted;','return KERN_SUCCESS;','ctx!=&videoToken','cls!=0||size!=0x20000','INTR(configGuard,IOAccelDeviceGetConfig)','memset(d,0,8);return KERN_SUCCESS;'):check(text in stage,'guard invariant '+text)
 specs=[('video-sierra-provider-20261027-01/0x2e27c.private.json',['0x2e2be: CALL 0x00032e12','0x2e2d6: CALL 0x00032e4e','0x2e2f2: CALL 0x00032e5a','0x2e306: CALL 0x00032e66','0x2e31e: MOV dword ptr [RBP + -0x44], 0x2','0x2e331: MOV ESI, 0x105','0x2e336: MOV ECX, 0x1','0x2e33d: CALL 0x00032e84']),('video-sierra-failed-ioaccel-static-20261027-01/0x2e45a.private.json',['0x2e494: CALL 0x00032e54','0x2e4b0: CALL 0x00032e1e'])]
 specs.append(('sierra-video-fence-path-20261027-01/0x2def8.private.json',['0x2df12: MOV qword ptr [RBX + 0x8], 0x20000','0x2e0f4: CALL 0x00032e00','0x2e0fb: JNZ 0x0002e111','0x2e106: CALL 0x00032dfa']))
 specs.append(('video-sierra-provider-20261027-01/0x2e27c.private.json',['0x2e3fa: CALL 0x0002def8','0x2e416: CALL 0x00032e6c','0x2e422: CALL 0x0002e45a']))
 evidence=[]
 for p,lines in specs:
  x=read(R/p)['result']['structuredContent'];check(x['subject']['digest']['sha256']==SHA,'REA target');v=x['raw_result']['value']
  for l in lines:check(l in v['assembly'],'missing instruction '+l)
  evidence.append({'file':p,'REA':x['evidence_id'],'sha256':sha(R/p)})
 rows=[];pids=set();intervals=[]
 for name,mode,status in CASES:
  p=R/name;i=read(p/'inputs.json');m=read(p/'execution/manifest.json');x=read(p/'result.json')
  check(i['build_manifest_SHA256']==sha(BUILD/'inputs.json') and x['mode']==mode and x['status']==status,'identity')
  check(m['arguments']==[i['candidate_path'],mode] and i['candidate_SHA256']==sha(i['candidate_path']),'arguments and candidate')
  check(m['exit_code']==0 and m['pid']==x['pid'] and m['pid'] not in pids and not m['SIGKILL_requested'] and m['GPU_reservation']['state']=='terminal' and m['GPU_reservation']['child_PID']==m['pid'] and not m['GPU_reservation']['known_signed_processes_live'] and not m['authoritative_ps_status'],'process');pids.add(m['pid'])
  check(sha(p/'application')==m['original_binary_sha256']==b['frozen']['application'] and sha(p/'execution/application')==m['signed_binary_sha256'] and read(p/'execution/execution.stdout')==x,'binary output')
  check(not x['hardware_video_execution_proved'] and not x['system_modified'] and not x['explicit_GPU_commands'] and not x['explicit_IOConnect_calls'] and not x['explicit_IOServiceOpen_calls'],'video claim or scope')
  if mode=='fence-probe':
   for k in ('provider_export_called','active_index_path_instruction_pin','IOAccel_guard_calibration','config_guard_calibrated','IOAccel_slot_pinned','all_eight_stage_slots_pinned','allocator_slot_pinned','initial_IOAccel_globals_zero','IOAccel_globals_restored','synthetic_initialization_used','zero_allocation_calibration','output_slot_zeroed','config_unchanged','output_296_zeroed','synthetic_guards_intact'):check(x[k],k)
   for k in ('IOAccel_device_guard_calls','synthetic_device_release_calls','synthetic_shared_create_calls','synthetic_shared_release_calls','synthetic_video_create_calls','synthetic_video_release_calls','synthetic_connection_calls','intercepted_scalar_calls','synthetic_80_byte_allocations_zeroed'):check(x[k]==1,k)
   for k in ('stage_unexpected_calls','pin_mismatch_mask'):check(x[k]==0,k)
   check(x['refused_device_config_calls']==1 and x['refused_after_fence_calls']==0,'post-fence local config refusal');check(x['intercepted_selector']==0x105 and x['intercepted_input_count']==1 and x['intercepted_output_capacity']==2 and x['intercepted_input0']==0,'scalar contract')
   check(x['request_guard_calls']==1 and x['request_class']==0 and x['request_size']==0x20000 and x['resource_get_calls']==1 and x['fence_guard_calls']==1 and x['synthetic_resource_released']==1 and not x['synthetic_resource_live'] and not x['other_data_guards_calls'],'request and fence contract')
   for k in ('guarded_IOServiceOpen_attempts','guarded_IOConnectCallMethod_attempts','guarded_IOConnectCallScalarMethod_attempts'):check(x[k]==0,k)
   check(not x['create_arguments_all_null'] and x['provider_return_code']==11 and x['symbols'][0]['called'] and not x['symbols'][1]['called'],'outcome')
  elif mode=='null-create':check(x['provider_export_called'] and x['create_arguments_all_null'] and x['provider_return_code']==5,'null')
  else:check(not x['provider_export_called'],'unexpected provider call')
  intervals.append((m['started_at'],m['completed_at']));rows.append({'case':name,'pid':m['pid'],'status':status,'result_SHA256':sha(p/'result.json')})
 intervals.sort();check(all(a[1]<=b[0] for a,b in zip(intervals,intervals[1:])), 'overlapping host processes')
 return {'status':'PASS','cohort':rows,'static_evidence':evidence,'limitations':['Device, shared and context objects and connection are synthetic; scalar method returns a fabricated success locally and data buffer is a fabricated token, and fence success is fabricated and no real decoding occurs.','Fence success is fabricated; config is refused without forwarding; no actual fence, config or GPU command is established.','The 80-byte provider allocation is deliberately zeroed, so this does not qualify normal behavior.','Sixteen prior import slots and the device-config slot are checked; other kernel paths and provider initializers are not exhaustively traced.','_exit skips dlclose; provider lifetime is not qualified.','Reservation is cooperative and does not exclude WindowServer.']}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--lab',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True);a=p.parse_args()
 B=a.lab.resolve();R=B/'results';BUILD=R/'video-sierra-fence-probe-build-20261027-03';GUARD=R/'video-ioaccel-guard-build-20261027-01';OLD=R/'video-sierra-provider-20261027-01/GeForceVADriver-10.12.6-x86_64.private'
 check(not a.out.exists(),'fresh output required');result=audit()
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps({'status':result['status'],'cases':len(result['cohort']),'hardware_video_execution_proved':False}))
