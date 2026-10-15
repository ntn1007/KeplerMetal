#!/usr/bin/env python3
"""Pin the opt-in argument runtime, selected qualification, and read-only OS check."""
from pathlib import Path
import datetime,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();out=ROOT/'results/argument-binding-runtime-progress-20261015'
v=json.loads((out/'final-verification.json').read_text());assert v['status']=='PASS'and v['total_final_candidate_scenarios']==192
lib=ROOT/'results/argument-binding-runtime-library-build-20261015-06';lm=json.loads((lib/'manifest.json').read_text());sources=[]
for rel,h in lm['source_SHA256'].items():assert sha(ROOT/rel)==h;sources.append({'path':rel,'SHA256':h,'bytes':(ROOT/rel).stat().st_size})
for rel in ['src/KeplerProgramImport.h','src/KeplerProgramImport.mm','src/gpu_command_frontend_dataflow.metal','src/cpu_icb_dependency.metal','src/cpu_icb_dependency_manifest.json','tools/build_command_ir_runtime_library.py','tools/build_public_argument_client.py','tools/command_ir_dataflow_client.mm','tools/PublicArgumentRefusals.inc','tools/verify_public_argument_delivery.py','tools/finalize_public_argument_stage.py','tools/verify_command_ir_dataflow.py','tools/verify_command_ir_lifetime.py','tools/run_command_ir_runtime.py','tools/run_command_ir_dataflow_qualification.py','tools/run_command_ir_lifetime_cases.py','tools/relink_command_ir_client.py']:
 p=ROOT/rel;sources.append({'path':rel,'SHA256':sha(p),'bytes':p.stat().st_size})
snapshot=hashlib.sha256(json.dumps(sorted(sources,key=lambda x:x['path']),sort_keys=True,separators=(',',':')).encode()).hexdigest()
(out/'source-snapshot-final.json').write_text(json.dumps({'files':sources,'snapshot_SHA256':snapshot},indent=2)+'\n')
base=json.loads((ROOT/'results/graphics-arguments-progress-20261015-03/system-and-source-check.json').read_text());system=[]
for r in base['system_files']:
 h=sha(r['path']);system.append({'path':r['path'],'baseline_SHA256':r['SHA256'],'current_SHA256':h,'unchanged':h==r['SHA256']})
oclp=sha('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist');assert all(r['unchanged']for r in system)and len(system)==83 and oclp==base['OCLP_SHA256']
assert sha(ROOT/'src/KeplerProgramImport.mm')=='24fea73a6b15b85fb0c6a15cf5a5a16ce69be890d8f67636eb8a97a87a72f326'
(out/'system-check-final.json').write_text(json.dumps({'status':'PASS','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'system_files_unchanged':83,'system_files':system,'OCLP_unchanged':True,'OCLP_SHA256':oclp},indent=2)+'\n')
env={k:subprocess.check_output(argv,text=True)for k,argv in {'OS':['sw_vers'],'SDK':['xcrun','--show-sdk-version'],'clang':['clang++','--version'],'CPU_RAM':['sysctl','-n','hw.memsize','machdep.cpu.brand_string']}.items()};(out/'environment.json').write_text(json.dumps(env,indent=2)+'\n')
totals={'exact_uint32_results':0,'consumer_invocations':0,'guard_bytes':0,'raw_files':0}
for r in v['rows']:
 n=r['verification'].get('numeric',r['verification'])
 for k in totals:totals[k]+=n.get(k,0)
receipt={'status':'PASS_SELECTED_QUALIFICATION','objective_complete':False,'goal_status':'active','git_branch':'main','git_HEAD':'UNBORN','source_snapshot_SHA256':snapshot,'candidate_library_SHA256':v['candidate_library_SHA256'],'previous_library_SHA256':'d88158307ed566d1a048f7f729c2896419c6836b3f44899ab6711a59850456fc','candidate_scenarios':192,'typed_binding_scenarios':68,'rejection_scenarios':84,'legacy_comparison_scenarios':4,'lifetime_regression_scenarios':36,'intentional_legacy_callback_cycle_controls':4,'legacy_semantic_files_equal':52,'M1_scenarios':12,'M1_semantic_files_equal':156,'same_client_source_SHA256':v['same_reception_source_SHA256'],'GTX_verification_totals':totals,'system_files_unchanged':83,'OCLP_unchanged':True,'integration_level':2,'native_Apple_ICB_identity':False,'three_pointer_GPU_qualification':'NOT RUN','broader_legacy_129_cohort_suite_on_new_library':'NOT RUN','performance_benchmark':'NOT RUN','Managed_abandonment_issue':'Previous native control FAIL remains; unrelated factory implementation unchanged','job_ids':[],'live_GPU_handles':[],'next_action':'Qualify three-pointer/other constant-position layouts and the function/library argument-encoder path for an ordinary reception client; preserve resource/identity/lifetime controls and full hardware scope.'}
(out/'qualification-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2))
