#!/usr/bin/env python3
"""Offline numerical, factory, restoration and cross-host delivery verification."""
from pathlib import Path
import argparse,hashlib,json,re
from verify_command_ir_dataflow import verify as numeric
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
sha=lambda f:hashlib.sha256(Path(f).read_bytes()).hexdigest()
library=ROOT/'results/native-pipeline-runtime-library-build-20261015';lm=json.loads((library/'manifest.json').read_text());pin=sha(library/'libKeplerMetal.a');assert pin==lm['static_library_SHA256']
for file,h in lm['source_SHA256'].items():assert sha(library/file)==sha(ROOT/file)==h,file
compiler=ROOT/'results/native-resource-command-compiler-build-20261015-02';cm=json.loads((compiler/'manifest.json').read_text());profiles={row['semantic']:row for row in cm['records']}
assert sha(compiler/'carrier.metallib')==cm['carrier_metallib_SHA256']
assert sha(ROOT/'src/KeplerNativeResourceLowering.inc')==cm['native_ABI_source_SHA256']
for semantic,row in profiles.items():
 assert sha(compiler/semantic/'program.sass')==row['code_SHA256']
 refs=re.findall(r'\bc(\d+)\[(0x[0-9a-f]+)\]',(compiler/('decode-'+semantic+'.stdout')).read_text())
 assert refs and all(bank=='1'for bank,off in refs)and any(off=='0x8'for bank,off in refs)
source=ROOT/'results/native-pipeline-command-client-build-20261015-02/command_ir_dataflow_client.mm'
s=source.read_text();assert 'writer=KPCreatePipeline('not in s and 'Push push='not in s and 'writer=[d newComputePipelineStateWithFunction:producerFunction error:&error]'in s
suite=ROOT/'results/native-pipeline-command-qualification-20261015';assert json.loads((suite/'status.json').read_text())['status']=='PASS'
history=json.loads((suite/'history.json').read_text());roots=[Path(row['result'])for row in history if row['phase']=='CPU'];assert len(roots)==16
results=[]
for root in roots:
 v=numeric(root);d=json.loads((root/'results.json').read_text());inp=json.loads((root/'inputs.json').read_text());assert inp['static_library_SHA256']==pin and inp['public_pipeline_factory']
 assert all(d[k]is True for k in ['public_pipeline_factory','native_root_binding','ordinary_pipeline_passthrough','unregistered_native_failure_preserved','native_factory_restored','scope_restored'])
 assert d['host_push_buffer_required']is False and d['producer_registration_refusals']==4
 events=d['function_events'];registered=[e for e in events if e['operation']=='register_IRv2_native_producer'];called=[e for e in events if e['operation']=='new_registered_IRv2_pipeline'];assert len(registered)==1 and len(called)==2
 profile=registered[0]['profile'];semantic=profile['function'].removeprefix('encode_dataflow_');assert profile['program_SHA256']==profiles[semantic]['code_SHA256']and profile['carrier_SHA256']==cm['carrier_metallib_SHA256']and profile['import']==d['producer_import']
 assert all(e['selector']=='newComputePipelineStateWithFunction:error:'and e['native_pipeline']and e['native_root_binding']for e in called)
 assert len([e for e in events if e['operation']=='restore_IRv2_functions'])==1
 results.append({'directory':str(root.relative_to(ROOT)),**{k:v[k]for k in ['mode','trials','exact_uint32_results','consumer_invocations','guard_bytes','API_refusals','raw_files']}})
reject=ROOT/'results/native-pipeline-argument-refusals-20261015';rd=json.loads((reject/'results.json').read_text());rm=json.loads((reject/'execution/manifest.json').read_text());ri=json.loads((reject/'inputs.json').read_text())
assert ri['static_library_SHA256']==pin and rm['exit_code']==0 and not rm['authoritative_ps_status']and not rm['SIGKILL_requested']and rd['scope_restored']and rd['argument_refusal_probe']and not list((reject/'outputs').iterdir())
rejections=[r for row in rd['runs']for r in row['argument_refusals']];assert len(rejections)==84
for row in rejections:assert all(row[k]is True for k in ['PASS','parameters_unchanged','plan_released','encoder_released'])and not row['user_kernel_submitted']and row['reason']
registration=ROOT/'results/native-pipeline-registration-20261015';reg=json.loads((registration/'results.json').read_text());regm=json.loads((registration/'execution/manifest.json').read_text());assert regm['exit_code']==0 and not regm['authoritative_ps_status']and len(reg['runs'])==4
for row in reg['runs']:
 assert all(row[k]is True for k in ['scope_released','function_class_restored','native_getter_restored','native_pipeline_survived_scope','native_factory_restored'])
 assert not row['GPU_dispatch']and not row['command_buffers_submitted']and all(x['PASS']for x in row['checks'])
reference=ROOT/'results/native-pipeline-M1-return-20261015/Reference';assert sha(reference/'command_ir_dataflow_client.mm')==sha(source)
common=['input','dummySrc','stage0','stage1','stage2','counter','dummyCounter']+['dummy'+str(i)for i in range(6)];matches=[];native=[]
for mode in ['no_producer','barrier','no_consumer']:
 root=reference/'results'/mode;native.append(numeric(root));gtx=ROOT/'results'/('native-pipeline-command-final-20261015-'+mode)
 for trial in range(4):
  for name in common:
   file=f'trial-{trial}-{name}.bin';left=gtx/'outputs'/file;right=root/'outputs'/file;assert left.read_bytes()==right.read_bytes(),(mode,file);matches.append({'mode':mode,'file':file,'SHA256':sha(left)})
baseline=json.loads((ROOT/'results/argument-binding-runtime-progress-20261015/system-check-final.json').read_text());systems=[]
for row in baseline['system_files']:
 actual=sha(row['path']);assert actual==row['baseline_SHA256'];systems.append({'path':row['path'],'baseline_SHA256':row['baseline_SHA256'],'current_SHA256':actual,'unchanged':True})
oclp=sha('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist');assert oclp=='72abe6b6100a53aa35269ca7e8ede7bc0e26f0be9140494b56c64f78672726d8'
report={'status':'PASS','static_library_SHA256':pin,'native_abi_compiler_SHA256':cm['compiler_SHA256'],'producer_source_metallib_SHA256':cm['producer_metallib_SHA256'],'native_carrier_SHA256':cm['carrier_metallib_SHA256'],'cohorts':results,'trials':sum(x['trials']for x in results),'exact_uint32_results':sum(x['exact_uint32_results']for x in results),'consumer_invocations':sum(x['consumer_invocations']for x in results),'guard_bytes':sum(x['guard_bytes']for x in results),'registration_refusals':4*len(results),'argument_refusals':84,'metadata_lifetime_trials':4,'metadata_checks':sum(len(x['checks'])for x in reg['runs']),'M1_client_SHA256':sha(source),'M1_trials':12,'M1_raw_matches':matches,'system_files':systems,'OCLP_SHA256':oclp,'performance_benchmark':False,'new_GPU_tests_in_verifier':False,'installed_native_compiler_replaced':False,'ordinary_unregistered_applications_supported':False,'full_objective_complete':False,'next':'Descriptor/reflection/asynchronous pipeline APIs, automatic function/library integration, broader hardware/driver categories'}
out=a.out.resolve();out.relative_to(ROOT/'results');out.parent.mkdir(parents=True,exist_ok=True)
with out.open('x')as f:json.dump(report,f,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in report.items()if k not in ['cohorts','M1_raw_matches','system_files']},indent=2))
