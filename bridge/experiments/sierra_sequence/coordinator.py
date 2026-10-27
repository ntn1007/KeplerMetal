#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Own-process Sierra active index with blocked IOAccel and synthetic allocation initialization; no private GPU calls.

Loading executes vendor and system initializers. On exit the process bypasses
provider destructors; this does not validate lifecycle, decoding or GPU work.
"""
import argparse,hashlib,json,os,pathlib,plistlib,shutil,subprocess,sys
B=pathlib.Path(__file__).resolve().parents[1]
OLD=B/'results/video-sierra-provider-20261027-01/GeForceVADriver-10.12.6-x86_64.private'
WRONG=B/'results/video-enumeration-progress-20261018/AppleGVA-10.13.6-x86_64.private.macho'
RUNTIME=B/'results/video-alias-native-build-20261027-04/runtime'
PROOF=B/'results/video-channel-class-map-20261027-01/audit-05.json'
OLD_SHA='bf2110a8a74786fe06da672e35f05a0dbd554aa651a83bacf02753c5899ef567';WRONG_SHA='54dc80c41bab45492d1eb601fb1d242b513107645d068bf24edee155b965681f'
PROOF_SHA='35147e0bd7231ff951f0c1a18e212ff180139a66da0911ff94133a597dea9e33'
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(pathlib.Path(p).read_text())
def save(p,x):
 with pathlib.Path(p).open('x') as f:json.dump(x,f,indent=2,sort_keys=True);f.write('\n')
def check(ok,msg):
 if not ok:raise ValueError(msg)
def profile(public):
 sys.path.insert(0,str(public));from video_metal_resource_observer import check_profile
 p=check_profile(); rows=plistlib.loads(subprocess.check_output(['ioreg','-a','-w0','-r','-c','nvAccelerator'],timeout=20))
 check(len(rows)==1 and rows[0].get('IORegistryEntryID')==4294968416 and rows[0].get('IORegistryEntryName')=='nvAccelerator','GPU identity changed')
 return p
def verify_inputs():
 evidence=B/'results/device-object-final-audit-20261027-01.json';check(sha(evidence)=='94bc05d92498408220574b762ce5c2f95138ffbe134cdb49a5eb78c6eb18da5b' and load(evidence)['configuration_words']==[768,0,0,0,1] and load(evidence)['status']=='PASS','Real configuration evidence differs')
 check(sha(OLD)==OLD_SHA and sha(WRONG)==WRONG_SHA and sha(PROOF)==PROOF_SHA,'candidate or qualification evidence changed')
 x=load(PROOF);check(x['status']=='STATIC_CLASS_MAPPING_PASS' and x['provider_initializers_statically_listed']==35 and not x['hardware_execution_proved'],'qualification evidence invalid')
 check(not x['initializer_graph_direct_gpu_imports'],'direct GPU calls in initializer graph need review')
 guard=B/'results/video-ioaccel-guard-build-20261027-01';g=load(guard/'inputs.json')
 for name,digest in g['frozen'].items():check(sha(guard/name)==digest,'guard prior input changed: '+name)
def build(a):
 verify_inputs();p=profile(a.public_tools.resolve());out=a.out.resolve();check(not out.exists() and out.parent.is_dir(),'new output required');out.mkdir()
 shutil.copy2(B/'tools/video_sierra_config_sequence_probe.mm',out/'loader.mm');shutil.copy2(B/'tools/video_ioaccel_config_sequence_guard.mm',out/'stage-guard.mm');shutil.copy2(B/'tools/video_sierra_zero_allocation.mm',out/'zero-observer.mm');shutil.copy2(B/'tools/video_sierra_zero_alloc_control.mm',out/'zero-control.mm');shutil.copy2(pathlib.Path(__file__),out/'coordinator.py');shutil.copytree(RUNTIME,out/'runtime')
 common=['xcrun','clang++','-arch','x86_64','-O2','-std=c++17'];observer=out/'libZeroObserver.dylib';control=out/'libZeroControl.dylib';guard=B/'results/video-ioaccel-guard-build-20261027-01'
 for source,lib in [('zero-observer.mm',observer),('zero-control.mm',control)]:
  c=common+['-dynamiclib',str(out/source),'-install_name',str(lib),'-o',str(lib)];q=subprocess.run(c,capture_output=True,text=True,timeout=90);check(q.returncode==0,'control library build: '+q.stderr);q=subprocess.run(['codesign','--force','--sign','-',str(lib)],capture_output=True,text=True,timeout=90);check(q.returncode==0,'control library sign')
 stage=out/'libStageGuard.dylib';sdk=subprocess.check_output(['xcrun','--show-sdk-path'],text=True).strip();c=common+['-dynamiclib',str(out/'stage-guard.mm'),str(guard/'libFakeTarget.dylib'),'-F'+sdk+'/System/Library/PrivateFrameworks','-framework','IOAccelerator','-framework','IOKit','-install_name',str(stage),'-o',str(stage)];q=subprocess.run(c,capture_output=True,text=True,timeout=90);check(q.returncode==0,'stage guard build: '+q.stderr);q=subprocess.run(['codesign','--force','--sign','-',str(stage)],capture_output=True,text=True,timeout=90);check(q.returncode==0,'stage guard sign')
 cmd=common+[str(stage),str(observer),str(control),str(guard/'libFakeClient.dylib'),str(guard/'libFakeTarget.dylib'),str(out/'loader.mm'),'-framework','Foundation','-framework','IOKit','-o',str(out/'application')]
 r=subprocess.run(cmd,capture_output=True,text=True,timeout=90);save(out/'commands.json',{'argv':cmd,'exit_code':r.returncode,'stdout':r.stdout,'stderr':r.stderr});check(r.returncode==0,'compiler failed')
 files=['loader.mm','stage-guard.mm','libStageGuard.dylib','zero-observer.mm','zero-control.mm','libZeroObserver.dylib','libZeroControl.dylib','coordinator.py','application','commands.json','runtime/lab_gpu_reservation.py','runtime/run_sdk_host.py']
 save(out/'inputs.json',{'profile':p,'user_UID':os.getuid(),'frozen':{name:sha(out/name) for name in files},'candidate_SHA256':OLD_SHA,'wrong_image_SHA256':WRONG_SHA,'preflight_audit_SHA256':PROOF_SHA,'vendor_load_executed_in_build':False})
 print(json.dumps({'status':'BUILD_PASS','application_SHA256':sha(out/'application')}))
def run(a):
 verify_inputs();build=a.build.resolve();out=a.out.resolve();data=load(build/'inputs.json');check(not out.exists() and out.parent.is_dir(),'new output required')
 for name,digest in data['frozen'].items():check(sha(build/name)==digest,'build changed '+name)
 check(sha(pathlib.Path(__file__))==data['frozen']['coordinator.py'],'coordinator changed');check(profile(a.public_tools.resolve())==data['profile'] and os.getuid()==data['user_UID'],'profile or user changed')
 out.mkdir();shutil.copy2(build/'application',out/'application');shutil.copy2(build/'loader.mm',out/'loader.mm');shutil.copy2(build/'coordinator.py',out/'coordinator.py');shutil.copytree(build/'runtime',out/'runtime')
 candidate=WRONG if a.mode=='wrong' else OLD
 save(out/'inputs.json',{'mode':a.mode,'candidate_path':str(candidate),'candidate_SHA256':sha(candidate),'build_manifest_SHA256':sha(build/'inputs.json'),'preflight_audit_SHA256':PROOF_SHA,'user_UID':os.getuid(),'candidate_owns_file_lifetime':False})
 sys.path.insert(0,str(out/'runtime'));from run_sdk_host import run_host
 manifest=run_host(out/'application',out/'execution',[str(candidate),a.mode],B)
 check(profile(a.public_tools.resolve())==data['profile'],'profile changed after execution');verify_inputs()
 result=load(out/'execution/execution.stdout');check(result['pid']==manifest['pid'] and result['mode']==a.mode and result['provider_export_called']==(a.mode in ('null-create','sequence-probe')) and not result['hardware_video_execution_proved'],'result identity')
 if a.mode=='null-create':check(result['status']=='NULL_CREATE_REJECTED' and result['null_path_instruction_pin'] and result['provider_return_code']==5 and result['create_arguments_all_null'] and not result['guarded_IOServiceOpen_attempts'] and not result['guarded_IOConnectCallMethod_attempts'] and not result['guarded_IOConnectCallScalarMethod_attempts'],'null path mismatch')
 if a.mode=='sequence-probe':check(result['status']=='SYNTHETIC_SEQUENCE_PROBE' and result['provider_return_code']==11 and result['active_index_path_instruction_pin'] and result['all_eight_stage_slots_pinned'] and result['intercepted_scalar_calls']==5 and result['config_guard_calibrated'] and result['sequence_guard_calibrated'] and result['sequence']==[0x103,0x104,0x102,0x100] and result['simulated_device_config_calls']==1 and result['refused_after_fence_calls']==1 and result['refused_after_fence_selector']==0x100 and result['fence_guard_calls']==1 and result['IOAccel_globals_restored'] and not result['guarded_IOServiceOpen_attempts'] and not result['guarded_IOConnectCallMethod_attempts'] and not result['guarded_IOConnectCallScalarMethod_attempts'],'synthetic post-fence probe mismatch')
 save(out/'result.json',result);print(json.dumps({'status':result['status'],'mode':a.mode,'pid':manifest['pid'],'loaded':result['loaded'],'hardware_video_execution_proved':False}))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('action',choices=['build','run']);p.add_argument('--out',type=pathlib.Path,required=True);p.add_argument('--public-tools',type=pathlib.Path,required=True);p.add_argument('--build',type=pathlib.Path);p.add_argument('--mode',choices=['inspect','wrong','missing','load','null-create','sequence-probe']);a=p.parse_args()
 if a.action=='build':build(a)
 else:
  if not a.build or not a.mode:p.error('--build and --mode required')
  run(a)
