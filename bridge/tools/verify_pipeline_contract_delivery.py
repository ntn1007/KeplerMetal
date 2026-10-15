#!/usr/bin/env python3
"""Offline audit of factory variants, numeric GPU outputs, CAS and lifetimes."""
from pathlib import Path
import argparse,hashlib,json
from verify_command_ir_dataflow import verify as numeric
from verify_native_cas_sdk import verify as cas_numeric
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
lib=ROOT/'results/pipeline-contract-runtime-library-build-20261015-04';lm=json.loads((lib/'manifest.json').read_text());pin=sha(lib/'libKeplerMetal.a');assert pin==lm['static_library_SHA256']
for name,h in lm['source_SHA256'].items():assert sha(lib/name)==sha(ROOT/name)==h,name
suite=ROOT/'results/pipeline-contract-factory-qualification-20261015';status=json.loads((suite/'status.json').read_text());assert status['status']=='PASS'and status['trials']==128
history=json.loads((suite/'history.json').read_text());cases=[]
for record in history:
 if record['phase']!='CPU':continue
 root=Path(record['result']);kind=record['factory_kind'];mode=record['mode'];v=numeric(root);d=json.loads((root/'results.json').read_text());inp=json.loads((root/'inputs.json').read_text());execution=json.loads((root/'execution/manifest.json').read_text())
 assert inp['static_library_SHA256']==pin and d['factory_kind']==kind and d['mode']==mode and execution['arguments'][-1]==f'{kind}:{mode}'
 e=d['factory_evidence'];assert e['kind']==kind and e['requested_max_threads']==0 and e['max_threads']==1024
 assert e['callbacks']==(1 if kind>=3 else 0)
 if kind>=3:assert e['off_thread']
 if kind in [1,2,4,5]:assert e['reflection']and e['reflection_class']=='KPIRComputeReflection'and e['members']==[{'index':i,'offset':8*i,'type':80 if i==0 else 79 if i==1 else 60}for i in range(6)]
 else:assert not e['reflection']
 if kind in [2,5]:assert e['label'].startswith('reception-encode_dataflow_')
 if kind==5:assert e['descriptor_mutation_ignored']
 cases.append({'factory_kind':kind,'mode':mode,**{k:v[k]for k in ['trials','exact_uint32_results','consumer_invocations','guard_bytes','raw_files']}})
cpu=ROOT/'results/registered-pipeline-pending-probe-20261015';cd=json.loads((cpu/'results.json').read_text());cm=json.loads((cpu/'execution/manifest.json').read_text());ci=json.loads((cpu/'inputs.json').read_text());assert ci['static_library_SHA256']==pin and cm['exit_code']==0 and not cm['SIGKILL_requested']and not cm['authoritative_ps_status']and len(cd['runs'])==42 and all(row['PASS']for row in cd['runs'])and cd['scope_released_with_reflection_alive']and not cd['command_buffers_submitted']
pending=[row for row in cd['runs']if row['kind']=='pending_scope_release'];assert len(pending)==1 and pending[0]['scope_released_before_callback']and pending[0]['early_callbacks']==0 and pending[0]['factory_method_restored']
native=cd['descriptor_defaults']['native_descriptor_diagnostic'];assert native['pipeline']and native['max_threads']==1024 and native['proof']['contract_verified']and cd['descriptor_defaults']['shader_validation']=='selector_unavailable'
cas=cas_numeric(ROOT/'results/pipeline-contract-cas-execute-20261015');negative=cas_numeric(ROOT/'results/pipeline-contract-cas-negative-20261015');assert cas['status']=='PASS'and negative['status']=='PASS'
for name in ['execute','negative']:
 root=ROOT/'results'/('pipeline-contract-cas-'+name+'-20261015');d=json.loads((root/'results.json').read_text());assert d['descriptor_transport_prelude']and d['descriptor_transport_import']['contract_verified']
comparison=json.loads((ROOT/'results/pipeline-contract-runtime-progress-20261015/M1-comparison.json').read_text());assert comparison['status']=='PASS'and len(comparison['matches'])==156
reference=ROOT/'results/pipeline-contract-M1-return-20261015/Reference';client=ROOT/'results/pipeline-contract-reception-client-build-20261015-02';assert sha(reference/'command_ir_dataflow_client.mm')==sha(client/'command_ir_dataflow_client.mm')==comparison['identical_client_SHA256'];assert sha(reference/'PipelineFactoryReception.inc')==sha(client/'PipelineFactoryReception.inc')
for mode in ['no_producer','barrier','no_consumer']:
 d=json.loads((reference/'results'/mode/'results.json').read_text());assert d['factory_kind']==5 and d['factory_evidence']['callbacks']==1 and d['factory_evidence']['reflection'];assert numeric(reference/'results'/mode)['status']=='PASS'
for row in comparison['matches']:
 left=ROOT/'results'/('pipeline-contract-final-20261015-k5-'+row['mode'])/'outputs'/row['file'];right=reference/'results'/row['mode']/'outputs'/row['file'];assert sha(left)==sha(right)==row['SHA256']
baseline=json.loads((ROOT/'results/argument-binding-runtime-progress-20261015/system-check-final.json').read_text());systems=[]
for row in baseline['system_files']:
 h=sha(row['path']);assert h==row['baseline_SHA256'];systems.append({'path':row['path'],'baseline_SHA256':row['baseline_SHA256'],'current_SHA256':h,'unchanged':True})
oclp=sha('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist');assert oclp=='72abe6b6100a53aa35269ca7e8ede7bc0e26f0be9140494b56c64f78672726d8'
report={'status':'PASS','static_library_SHA256':pin,'source_manifest_SHA256':sha(lib/'manifest.json'),'factories':6,'GPU_cohorts':len(cases),'GPU_trials':sum(x['trials']for x in cases),'exact_uint32_results':sum(x['exact_uint32_results']for x in cases),'consumer_invocations':sum(x['consumer_invocations']for x in cases),'guard_bytes':sum(x['guard_bytes']for x in cases),'cases':cases,'CPU_supported_variants':17,'CPU_rejections':24,'pending_scope_release_cases':1,'CAS_regression':{k:v for k,v in cas.items()if k!='records'},'CAS_negative_controls':negative,'M1_same_client_SHA256':comparison['identical_client_SHA256'],'M1_trials':12,'M1_common_files':156,'system_files':systems,'OCLP_SHA256':oclp,'descriptor_smaller_limit_supported':False,'shaderValidation_selector_available':False,'new_GPU_tests_in_verifier':False,'performance_benchmark':False,'full_objective_complete':False,'next':'Correct smaller thread-limit semantics, additional descriptor contracts, automatic library/function integration and the remaining NVIDIA hardware/driver categories'}
out=a.out.resolve();out.relative_to(ROOT/'results');out.parent.mkdir(parents=True,exist_ok=True)
with out.open('x')as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in report.items()if k not in ['cases','system_files']},indent=2))
