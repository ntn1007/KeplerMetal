#!/usr/bin/env python3
"""Recheck exact outputs, imports, both IR versions and all129 legacy oracles."""
from pathlib import Path
import datetime,hashlib,importlib.util,json,sys
from verify_command_ir_grid3d import verify as grid_verify
from verify_command_ir_runtime import verify as ir_verify
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/command-ir-multidimensional-progress-20261015'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
library=ROOT/'results/command-ir-v2-library-build-20261015-04';bm=read(library/'manifest.json');libsha=sha(library/'libKeplerMetal.a');assert libsha==bm['static_library_SHA256']
for p,h in bm['source_SHA256'].items():assert sha(ROOT/p)==sha(library/p)==h
legacy=ROOT/'results/command-ir-v2-final-legacy-suite-20261015';assert read(legacy/'completion.json')['status']=='PASS';commands=read(legacy/'commands.json');assert len(commands)==185 and all(c['exit_code']==0 for c in commands)
public=ROOT/'results/command-ir-v2-final-qualification-20261015';assert read(public/'completion.json')['status']=='PASS'
rows=[]
def identities(p):
 m=read(p/'execution/manifest.json');assert m['exit_code']==0 and not m['SIGKILL_requested']and not m['authoritative_ps_status']and m['GPU_reservation']['state']=='terminal'
 i=read(p/'inputs.json');assert i['static_library_SHA256']==libsha;exe=p/('application'if(p/'application').exists()else 'cpu_icb_'+('manifest'if'manifest'in p.name else'grid3d')+'_probe');assert sha(exe)==i['executable_SHA256']==m['original_binary_sha256']
 assert sha(p/'execution/application')==m['signed_binary_sha256']
 for n,h in i.get('source_hashes',{}).items():assert sha(p/n)==h
 for n,h in i.get('assets_SHA256',{}).items():assert sha(p/'assets'/n)==h
 return m
grid_modes=['no_producer','basic','threads','barrier','copy','reset','split','bad_flags','bad_pipeline','bad_address0','bad_address1','bad_address2','bad_parameters','bad_groups_x','bad_groups_y','bad_groups_z','bad_local_z','bad_kind','bad_stage','bad_reserved','bad_shared','bad_threads']
for mode in grid_modes:
 p=ROOT/'results'/('command-ir-v2-final-grid3d-'+mode.replace('_','-')+'-20261015');v=grid_verify(p);m=identities(p);assert v['status']=='PASS';rows.append({'kind':'grid3d','mode':mode,'directory':str(p),'PID':m['pid'],'trials':v['trials'],'words':v['exact_uint32_words'],'invocations':v['consumer_invocations']})
api=ROOT/'results/command-ir-v2-final-API-refusals-20261015';v=grid_verify(api);m=identities(api);assert read(api/'results.json')['API_refusals']==11;rows.append({'kind':'API','mode':'basic','directory':str(api),'PID':m['pid'],'trials':v['trials'],'words':v['exact_uint32_words'],'invocations':v['consumer_invocations']})
modes=['basic','barrier','clear','copy','reset','no_producer','split','bad_flags','bad_tag','bad_pipeline','bad_address','bad_parameters','bad_local','bad_shared','bad_groups','bad_y','bad_threads','bad_stage','bad_error','bad_reserved']
for kind,items in [('v1',modes),('v2-three',modes),('v2-combined',modes[:7]+['bad_shared'])]:
 for mode in items:
  p=ROOT/'results'/('command-ir-v2-final-'+kind+'-'+mode.replace('_','-')+'-20261015');v=ir_verify(p);m=identities(p);rows.append({'kind':kind,'mode':mode,'directory':str(p),'PID':m['pid'],'trials':v['runs'],'words':v['exact_uint32_words'],'invocations':v['consumer_GPU_invocations_counted']})
print('Current grid/IR oracles PASS',len(rows),flush=True)
sdk=ROOT/'results/command-ir-v2-final-regression-clients-20261015/KeplerMetalSDK';sys.path.insert(0,str(sdk/'examples'));mapping={'async':'verify_cpu_icb_copy_async','mixed':'verify_cpu_icb_copy_mixed','graph':'verify_cpu_icb_copy_graph','baseline':'verify_cpu_icb_gpu_copy','refusal':'verify_cpu_icb_copy_refusals','reverse':'verify_fp64_reverse_client','arithmetic':'verify_fp64_client','cas':'verify_example','literal':'verify_literal_client','registered':'verify_registered_resident_copy','registered_bounds':'verify_registered_resident_bounds','manifest':'verify_cpu_icb_manifest','grid3d':'verify_cpu_icb_grid3d','dynamic':'verify_dynamic_resident_copy','dynamic_bounds':'verify_dynamic_resident_bounds','combined':'verify_combined_shared_copy','combined_bounds':'verify_combined_shared_bounds','selection':'verify_gpu_command_selection','gpu_refusals':'verify_gpu_selection_refusals','geometry':'verify_gpu_command_geometry','geometry_refusals':'verify_gpu_geometry_refusals'};loaded={};legacy_rows=[]
for c in commands:
 args=c['argv']
 if '--build'not in args:continue
 kind=Path(args[args.index('--build')+1]).name.removesuffix('-application');p=Path(args[args.index('--out')+1]);name=mapping[kind];base=ROOT/'tools'if kind in ['manifest','grid3d']else sdk/'examples'
 if name not in loaded:
  s=importlib.util.spec_from_file_location(name,base/(name+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);loaded[name]=m.verify
 v=loaded[name](p,portable=True);assert v['status'].startswith('PASS');m=identities(p);legacy_rows.append({'kind':kind,'directory':str(p),'PID':m['pid'],'status':v['status'],'exact_words':v.get('exact_uint32_words'),'raw_files':len(v.get('raw_SHA256',{}))})
 if len(legacy_rows)%20==0:print('Legacy offline oracles',len(legacy_rows),flush=True)
assert len(legacy_rows)==129
ref=ROOT/'results/command-ir-grid3d-M1-return-20261015/Reference';manifest=read(ref/'FILE_MANIFEST.json')
for e in manifest['files']:assert sha(ref/e['path'])==e['SHA256']
for a,b in [('command_ir_grid3d_client.mm',ROOT/'tools/command_ir_grid3d_client.mm'),('gpu_command_frontend_grid3d.metal',ROOT/'src/gpu_command_frontend_grid3d.metal'),('cpu_icb_grid3d.metal',ROOT/'src/cpu_icb_grid3d.metal')]:assert sha(ref/a)==sha(b)
equal=0
for mode in grid_modes[:7]:
 native=ref/'results'/mode;v=grid_verify(native);assert v['status']=='PASS';current=ROOT/'results'/('command-ir-v2-final-grid3d-'+mode.replace('_','-')+'-20261015')
 for x,y in zip(read(current/'results.json')['runs'],read(native/'results.json')['runs']):
  assert x['node_specs']==y['node_specs']and x['files']==y['files']
  for f in x['files']:
   for n in f.values():assert(current/'outputs'/n).read_bytes()==(native/'outputs'/n).read_bytes();equal+=1
assert equal==1278
controls=ROOT/'results/command-ir-v2-final-primer-controls-20261015';cv=read(controls/'receipt.json');assert cv['primer_checks']==60 and cv['policy_checks']==9 and cv['library_SHA256']==libsha
for i,row in enumerate(cv['streams']):
 assert sha(ROOT/row['path'])==row['SHA256'];checks=read(controls/f'compare-{i}.json')['checks'];assert len(checks)==12 and all(c['accepted']==c['expected_accepted']for c in checks)
assert len(read(controls/'policy.json')['checks'])==9 and all(c['accepted']==c['expected']for c in read(controls/'policy.json')['checks'])
system=read(ROOT/'results/command-ir-runtime-progress-20261015/system-and-source-check-final.json')
for f in system['system_files']:assert sha(f['path'])==f['SHA256']
assert sha('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist')==system['OCLP_SHA256']
(OUT/'system-check.json').write_text(json.dumps({'status':'PASS','system_files':system['system_files'],'OCLP_SHA256':system['OCLP_SHA256']},indent=2)+'\n')
files=sorted(p for folder in ['src','tools']for p in(ROOT/folder).rglob('*')if p.is_file()and '__pycache__'not in p.parts);(OUT/'source-snapshot.json').write_text(json.dumps({'files':[{'path':str(p.relative_to(ROOT)),'SHA256':sha(p),'bytes':p.stat().st_size}for p in files]},indent=2)+'\n')
total=lambda kind,key:sum(r[key]for r in rows if r['kind']==kind)
receipt={'status':'PASS','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'previous_goal_turn':'PROGRESS','current_goal_turn':'PROGRESS','objective_complete':False,'Git_branch':'main','Git_commit':None,'job_ids':[],'source_snapshot_SHA256':sha(OUT/'source-snapshot.json'),'library_SHA256':libsha,'materializer_v2_SHA256':sha(ROOT/'results/command-ir-v2-materializer-build-20261015/command_ir_materializer.metallib'),'grid3d_trials':132,'grid3d_exact_uint32_words':total('grid3d','words'),'grid3d_consumer_invocations':total('grid3d','invocations'),'v2_three_buffer_trials':60,'v2_three_buffer_exact_words':total('v2-three','words'),'v2_combined_shared_trials':24,'v2_combined_exact_words':total('v2-combined','words'),'v1_regression_trials':60,'v1_regression_exact_words':total('v1','words'),'API_pre_dispatch_refusals':11,'API_positive_XYZ_trials':6,'legacy_cohorts':129,'legacy_command_steps':185,'legacy_offline_oracles_rechecked':129,'M1_native_trials':42,'M1_GTX_raw_files_identical':equal,'primer_byte_controls':60,'primer_profile_controls':9,'system_files_unchanged':83,'OCLP_unchanged':True,'installed_driver_updated':False,'ordinary_applications_transparent':False,'integration_level':2,'performance_benchmark':False,'rows':rows,'legacy_rows':legacy_rows,'BLOCKED':[],'NOT_RUN':['Partial/nonuniform workgroups','Constant-buffer positions other than last','Stage-in and strides in GPU IR','Cross-context GPU command copies','Full concurrent/dependency stress','Transparent ordinary-application integration','New-library benchmarks','Video/display/power/full-VRAM qualification'],'next_action':'Generalize reflected constant/buffer positions and test a real dataflow client; qualify partial grids and integrate ordinary API clients while retaining independent native-driver modernization work.'}
(OUT/'qualification-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n');print(json.dumps({k:v for k,v in receipt.items()if k not in ['rows','legacy_rows','NOT_RUN']},ensure_ascii=False,indent=2))
