#!/usr/bin/env python3
"""Recheck final caller ownership, independent numbers, unchanged core and system."""
from pathlib import Path
import datetime,hashlib,json,subprocess
from verify_command_ir_dataflow import verify as flow_verify
from verify_command_ir_lifetime import verify as life_verify
from verify_command_ir_grid3d import verify as grid_verify
from verify_command_ir_runtime import verify as ir_verify
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/command-ir-lifetime-progress-20261015';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();read=lambda p:json.loads(Path(p).read_text())
final=ROOT/'results/command-ir-lifetime-final-qualification-20261015';assert read(final/'completion.json')['status']=='PASS'
core=ROOT/'results/command-ir-dataflow-library-build-20261015-03';bm=read(core/'manifest.json');libsha=sha(core/'libKeplerMetal.a');assert libsha==bm['static_library_SHA256']
for n,h in bm['source_SHA256'].items():assert sha(ROOT/n)==sha(core/n)==h
old=ROOT/'results/command-ir-dataflow-progress-20261015/qualification-receipt.json';prior=read(old);assert prior['status']=='PASS'and prior['library_SHA256']==libsha and prior['legacy_cohorts']==129
header=ROOT/'src/KeplerProgramImport.h';assert header.read_text().count('NS_RETURNS_RETAINED')==6
contract=read(ROOT/'results/command-ir-lifetime-return-contract-recheck-20261015/receipt.json');assert contract['status']=='PASS'and contract['candidate_header_SHA256']==sha(header)
assert contract['results']['legacy']['destroyed']==0 and contract['results']['annotated']['destroyed']==6
assert sha(ROOT/'src/KeplerProgramImport.mm')==contract['implementation_source_SHA256']
def identity(p,annotated=True):
 i=read(p/'inputs.json');m=read(p/'execution/manifest.json');assert i['static_library_SHA256']==libsha
 assert m['exit_code']==0 and not m['SIGKILL_requested']and not m['authoritative_ps_status']and m['GPU_reservation']['state']=='terminal'
 assert sha(p/'application')==i['executable_SHA256']==m['original_binary_sha256']and sha(p/'execution/application')==m['signed_binary_sha256']
 for n,h in i['source_hashes'].items():assert sha(p/n)==h
 for n,h in i['assets_SHA256'].items():assert sha(p/'assets'/n)==h
 if annotated:assert i['source_hashes']['KeplerProgramImport.h']==sha(header)
 return m
rows=[]
for name in ['cases','production-dataflow','production-regression']:
 suite=ROOT/'results'/('command-ir-lifetime-final-'+name+'-suite-20261015'if name in ['cases','production-dataflow']else'command-ir-lifetime-final-production-regression-20261015')
 history=read(suite/'history.json')
 for e in history:
  if e.get('phase')!='CPU':continue
  p=Path(e.get('directory',e.get('result')));kind='lifetime'if name=='cases'else'dataflow'if name=='production-dataflow'else e['kind'];v=(life_verify if kind=='lifetime'else flow_verify if kind=='dataflow'else grid_verify if kind=='grid3d'else ir_verify)(p);m=identity(p);assert v['status']=='PASS'
  n=v['numeric']if kind=='lifetime'else v
  rows.append({'kind':kind,'mode':v.get('variant',v.get('mode')),'directory':str(p),'PID':m['pid'],'trials':v.get('trials',v.get('runs')),'exact_words':n.get('exact_uint32_results',n.get('exact_uint32_words')),'counted_invocations':n.get('consumer_invocations',n.get('consumer_GPU_invocations_counted',0)),'negative_contract_witness':kind=='lifetime'and v['variant']=='cancel_legacy'})
assert len(rows)==43 and sum(x['trials']for x in rows)==169
pair=read(OUT/'real-return-ownership-pair.json');assert pair['status']=='PASS'
for label in ['legacy','annotated']:
 p=ROOT/'results'/('command-ir-lifetime-return-'+label+'-gpu-20261015');life_verify(p);identity(p,annotated=label=='annotated')
 a=read(p/'results.json');assert all(r['lifetime']['imported_writer_alive_after_release']==(label=='legacy')for r in a['runs'])
mi=read(OUT/'M1-comparison.json');assert mi['status']=='PASS'and mi['native_trials']==12 and mi['raw_files_identical']==156
ref=ROOT/'results/command-ir-lifetime-M1-return-20261015/Reference'
for e in read(ref/'REFERENCE_RETURN.json')['files']:assert sha(ref/e['path'])==e['SHA256']
for n,target in [('command_ir_dataflow_client.mm',ROOT/'tools/command_ir_dataflow_client.mm'),('KeplerCPUICB.h',ROOT/'src/KeplerCPUICB.h'),('gpu_command_frontend_dataflow.metal',ROOT/'src/gpu_command_frontend_dataflow.metal')]:assert sha(ref/n)==sha(target)
for mode in ['no_producer','barrier','no_consumer']:
 p=ref/'results'/mode;flow_verify(p);q=ROOT/'results'/('command-ir-lifetime-final-production-dataflow-20261015-'+mode)
 for a,b in zip(read(p/'results.json')['runs'],read(q/'results.json')['runs']):
  for name,f in a['files'].items():
   if name!='records':assert(p/'outputs'/f).read_bytes()==(q/'outputs'/b['files'][name]).read_bytes()
system=read(ROOT/'results/command-ir-runtime-progress-20261015/system-and-source-check-final.json')
for e in system['system_files']:assert sha(e['path'])==e['SHA256']
assert sha('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist')==system['OCLP_SHA256']
pids=[str(x['PID'])for x in rows];ps=subprocess.run(['ps','-o','pid=,lstart=,command=','-p',','.join(pids)],capture_output=True,text=True);assert not ps.stdout.strip()
files=sorted(p for folder in ['src','tools']for p in(ROOT/folder).rglob('*')if p.is_file()and'__pycache__'not in p.parts)
with(OUT/'source-snapshot.json').open('x')as f:json.dump({'Git_branch':'main','Git_commit':None,'files':[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'SHA256':sha(p)}for p in files]},f,indent=2);f.write('\n')
receipt={'status':'PASS','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'previous_goal_turn':'PROGRESS','current_goal_turn':'PROGRESS','objective_complete':False,'Git_branch':'main','Git_commit':None,'source_snapshot_SHA256':sha(OUT/'source-snapshot.json'),'library_SHA256':libsha,'materializer_SHA256':prior['materializer_v2_SHA256'],'import_header_SHA256':sha(header),'import_implementation_SHA256':sha(ROOT/'src/KeplerProgramImport.mm'),'runtime_library_source_and_bytes_unchanged':True,'prior_core_qualification_receipt_SHA256':sha(old),'prior_129_cohorts_reexecuted_this_phase':False,'prior_core_qualification_remains_same_binary':True,'final_GPU_cohorts':43,'final_trials':169,'lifetime_trials':36,'current_dataflow_trials':64,'other_caller_trials':69,'exact_uint32_results':sum(x['exact_words']for x in rows),'counted_consumer_invocations':sum(x['counted_invocations']for x in rows),'CPU_return_contract_factories':6,'real_GPU_return_AB_trials':8,'return_AB_raw_files_identical':16,'M1_native_trials':12,'M1_raw_files_identical':156,'system_files_unchanged':83,'OCLP_unchanged':True,'OCLP_SHA256':system['OCLP_SHA256'],'final_probe_PIDs_terminal':len(pids),'scope':'Own-process SDK/caller ownership and retained C return conventions; L2. No installed driver update. No global ARC/driver/cache lifetime claim.','job_ids':[],'performance_benchmark':False,'integration_level':2,'ordinary_applications_transparent':False,'rows':rows,'BLOCKED':[],'NOT_RUN':['GPU graphics/tessellation/NoCopy C factory deallocation with ARC callers','Long-lived concurrent cancellation and memory pressure/fullVRAM','Native argument-encoder ICB identity and transparent app integration','New-runtime performance','Video/display/power and Linux driver port'],'next_action':'Qualify remaining factory lifetimes, then the public argument-encoder/ICB boundary for a real application, preserving the full hardware/driver objective.'}
with(OUT/'qualification-receipt.json').open('x')as f:json.dump(receipt,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in receipt.items()if k not in ['rows','NOT_RUN']},indent=2))
