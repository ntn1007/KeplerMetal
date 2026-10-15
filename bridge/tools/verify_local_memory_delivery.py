#!/usr/bin/env python3
"""Audit native capacity observations, local/spill GPU results and regressions."""
from pathlib import Path
import argparse,hashlib,json,struct,re
from verify_local_memory import verify as numeric
from verify_native_cas_sdk import verify as cas_numeric
from verify_command_ir_dataflow import verify as ir_numeric
ROOT=Path(__file__).resolve().parents[1]
def load(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def terminal(root):
 m=load(root/'execution/manifest.json');assert m['exit_code']==0 and not m['SIGKILL_requested']and not m['authoritative_ps_status']and m['GPU_reservation']['state']=='terminal'
 inp=load(root/'inputs.json');assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256']
 for n,h in inp['source_hashes'].items():assert sha(root/n)==h
 for n,h in inp['assets_SHA256'].items():assert sha(root/'assets'/n)==h
 return inp
def verify():
 lib=ROOT/'results/local-memory-runtime-library-build-20261015-03';lm=load(lib/'manifest.json');pin=sha(lib/'libKeplerMetal.a');assert pin==lm['static_library_SHA256']
 for n,h in lm['source_SHA256'].items():
  assert sha(lib/n)==h;source=ROOT/n
  if not source.exists():assert n=='src/KeplerFP64Programs.inc';source=ROOT/'results/gpu-generated-bindings-sdk-build-20261014-02/KeplerMetalSDK/src/KeplerFP64Programs.inc'
  assert sha(source)==h
 programs=ROOT/'results/local-memory-programs-build-20261015-03';pm=load(programs/'manifest.json')
 for n,h in pm['source_SHA256'].items():assert sha(programs/n)==h
 assert sha(ROOT/'tools/local_memory_compile.c')==pm['source_SHA256']['local_memory_compile.c']
 for n,h in pm['archives_SHA256'].items():assert sha(ROOT/'build/mesa'/n)==h
 observations=ROOT/'results/local-memory-native-observations-20261015';od=load(observations/'observations.json');assert load(observations/'status.json')['status']=='PASS'and len(od['records'])==7
 native_sizes={};native_local_ops={}
 for row in od['records']:
  m=load(observations/row['function']/'execution/manifest.json');assert not m['exit_code']and not m['SIGKILL_requested']and not m['authoritative_ps_status']
  assert not row['GPU_dispatch']and len(row['payloads'])==1
  item=row['payloads'][0];capture=observations/row['function']/'capture'
  payload=next(capture.glob('program-*.compiler-output.bin'));assert sha(payload)==item['compiler_output_SHA256'];blob=payload.read_bytes();version,total=struct.unpack_from('<2I',blob);assert version in[7,8,9]and total==len(blob)
  offset=8;w=None;code=None
  for _ in range(32):
   next_,kind,size=struct.unpack_from('<QII',blob,offset);assert offset+16+size<=len(blob)
   if kind==0x10004:assert w is None and size==232;w=list(struct.unpack_from('<58I',blob,offset+16))
   if kind==0x10005:assert code is None;code=blob[offset+16:offset+16+size]
   if not next_:break
   assert next_>=16+size;offset+=next_
  assert w==item['metadata_words']and code==capture.joinpath('native-0.sass').read_bytes()
  assert len(w)==58 and w[9]==w[12]*64 and w[12]==w[13]and w[11]==0
  assert sha(capture/'native-0.sass')==item['code_SHA256']and sha(capture/'native-0.envydis.txt')==item['listing_SHA256']
  listing=(capture/'native-0.envydis.txt').read_text();assert [x for x in listing.splitlines()if re.search(r'\bl\[|\b(?:ldl|stl)\b',x)]==item['local_memory_instruction_lines']
  variant=next(capture.glob('program-*.variant.bin'));assert sha(variant)==item['variant_SHA256'];raw=variant.read_bytes();assert struct.unpack_from('<I',raw,40)[0]==((w[9]+1023)&~1023)+512
  assert struct.unpack_from('<I',raw,48)[0]==w[7]and struct.unpack_from('<I',raw,56)[0]==w[14]
  native_sizes[row['function']]=w[12];native_local_ops[row['function']]=len(item['local_memory_instruction_lines'])
 assert native_sizes=={'local_control':0,'local32':128,'local256':1024,'local1024':4096,'pressure32':0,'pressure64':24,'pressure96':224}
 assert native_local_ops['local_control']==native_local_ops['pressure32']==0 and native_local_ops['pressure64']>0 and native_local_ops['pressure96']>0
 for row in pm['programs']:
  assert load(programs/(row['name']+'.json'))==row['info']
  assert sha(programs/(row['name']+'.sass'))==row['code_SHA256'];assert '[unknown'not in(programs/(row['name']+'-decode.stdout')).read_text()
  if row['name']in['pressure64','pressure96','pressure32_forced_spill']:assert row['info']['spills_to_memory']>0 and row['info']['fills_from_memory']>0 and 0<row['info']['scratch_bytes']<=224
 qualifier=ROOT/'results/local-memory-extended-qualification-20261015';assert load(qualifier/'status.json')['status']=='PASS'
 cases=[];client=ROOT/'results/local-memory-import-probe-build-20261015-05'
 for h in load(qualifier/'history.json'):
  assert not h['exit_code']
  if h['phase']!='CPU':continue
  root=Path(h['result']);assert terminal(root)['static_library_SHA256']==pin
  assert sha(root/'local_memory_probe.mm')==sha(client/'local_memory_probe.mm')==sha(ROOT/'tools/local_memory_probe.mm')
  r=numeric(root);d=load(root/'results.json');assert len(d['runs'])==12 and d['trial_profile']=='extended'
  assert sorted({x['local']for x in d['runs']})==[1,31,32,33,64,128,256,512,1024]
  if h['mode'].startswith('nak:'):
   for e in d['import']['events']:
    if not e.get('code_replaced'):continue
    assert e['launch_words_9_11']==[e['carrier_local_bytes']*64,576]
    assert e['native_metadata_preserved_except_instruction_register_and_control']
   program=d['program'];assert root.joinpath('assets',program+'.sass').read_bytes()==programs.joinpath(program+'.sass').read_bytes()
  cases.append({'mode':h['mode'],**{k:v for k,v in r.items()if k!='files_SHA256'}})
 assert len(cases)==19 and sum(x['trials']for x in cases if x['kernel_dispatches'])==180 and sum(x['trials']for x in cases if not x['kernel_dispatches'])==48
 contracts=ROOT/'results/local-memory-contract-probe-20261015-02';assert terminal(contracts)['static_library_SHA256']==pin;cd=load(contracts/'results.json');assert len(cd['runs'])==14 and all(x['PASS']for x in cd['runs'])and cd['GPU_command_buffers']==0 and cd['legacy_config_bytes']==12
 assert cd['runs'][-1]['kind']=='valid_after_rejections'and cd['runs'][-1]['import']['contract_verified']
 regression=ROOT/'results/local-memory-progress-20261015';assert load(regression/'regression-status.json')['status']=='PASS'
 cas=[];cb=ROOT/'results/local-memory-CAS-regression-build-20261015';ci=load(cb/'inputs.json');assert ci['module_static_library_SHA256']==pin and sha(cb/'cas_example')==ci['executable_SHA256']and sha(cb/'cas_client.mm')==ci['client_source_SHA256']
 for n,h in ci['assets'].items():assert sha(cb/'assets'/n)==h
 for mode in ['execute','negative']:
  root=ROOT/'results'/('local-memory-CAS-'+mode+'-20261015');d=load(root/'results.json');assert d['local_memory_prelude']and d['descriptor_transport_prelude']and d['local_memory_import']['contract_verified']and d['descriptor_transport_import']['contract_verified'];cas.append(cas_numeric(root))
 ir=[]
 for name in ['plain','alias-async']:
  root=ROOT/'results'/('local-memory-library-'+name+'-20261015');assert terminal(root)['static_library_SHA256']==pin;ir.append(ir_numeric(root))
 first=ROOT/'results/local-memory-import-control-20261015';f=load(first/'results.json');assert all((first/'outputs'/x['output_file']).read_bytes()==b'\xa5'*x['output_bytes']for x in f['runs'])
 assert sha(first/'assets/local_control.sass')==sha(programs/'local_control.sass')
 assert all(e['launch_words_9_11']==[0,0]for e in f['import']['events']if e.get('code_replaced'))
 control=load(ROOT/'results/local-memory-import-control-20261015-04/results.json');assert all(e['launch_words_9_11']==[0,576]for e in control['import']['events']if e.get('code_replaced'))
 baseline=load(ROOT/'results/pipeline-contract-runtime-progress-20261015/final-verification.json');assert len(baseline['system_files'])==83
 for row in baseline['system_files']:assert sha(row['path'])==row['baseline_SHA256']
 assert sha('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist')==baseline['OCLP_SHA256']
 return {'status':'PASS','runtime_library_SHA256':pin,'runtime_source_manifest_SHA256':sha(lib/'manifest.json'),'client_SHA256':sha(client/'local_memory_probe.mm'),'programs_manifest_SHA256':sha(programs/'manifest.json'),'native_local_bytes':native_sizes,'native_local_instruction_counts':native_local_ops,'cohorts':len(cases),'positive_trials':180,'negative_trials':48,'exact_uint32_results':sum(x['exact_uint32_results']for x in cases),'witnessed_kernel_invocations':sum(x['exact_uint32_results']for x in cases)//4,'guard_bytes':sum(x['guard_bytes']for x in cases),'negative_expected_words_absent':sum(x['negative_expected_words_absent']for x in cases),'cases':cases,'contracts':14,'CAS_operations':cas[0]['correct_CAS_operations'],'CAS_rejection_controls':8,'CAS_after_local_and_descriptor_import':True,'library_regression_trials':sum(x['trials']for x in ir),'library_regression_uint32':sum(x['exact_uint32_results']for x in ir),'same_program_control_failure_preserved':True,'programs':pm['programs'],'source_version':'Mesa 26.2.4 extracted source; no nested Git checkout, effective linked archive hashes recorded','native_local_frame_limit_tested':4096,'external_CRS_support':False,'M1_reference':'NOT RUN for this local-memory cohort','system_files_unchanged':83,'OCLP_unchanged':True,'installed_driver_modified':False,'performance_benchmark':False,'full_objective_complete':False,'Qwen_job_ids':[]}
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();d=verify();out=a.out.resolve();out.relative_to(ROOT/'results')
 with out.open('x')as f:json.dump(d,f,indent=2);f.write('\n')
 print(json.dumps({k:v for k,v in d.items()if k not in['cases','programs']},indent=2))
