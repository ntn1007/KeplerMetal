#!/usr/bin/env python3
"""Audit manifest consumers, aligned threads and regressions before delivery."""
from pathlib import Path
import datetime,hashlib,json
from verify_command_ir_runtime import verify
from verify_gpu_command_bindings import verify as verify_bindings
from verify_m1_command_ir_manifest import verify as verify_m1
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/command-ir-manifest-qualification-20261015'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
for n in ['suite-complete.json','runtime-regression-complete.json','threads-complete.json','legacy-complete.json']:assert read(OUT/n)['status']=='PASS'
library=ROOT/'results/command-ir-general-library-build-20261015-05';build=read(library/'manifest.json');libsha=sha(library/'libKeplerMetal.a');assert libsha==build['static_library_SHA256']
for path,h in build['source_SHA256'].items():assert sha(ROOT/path)==sha(library/path)==h
for path,h in build['reused_object_SHA256'].items():assert sha(path)==h
modes=['basic','barrier','clear','copy','reset','no_producer','split','bad_flags','bad_tag','bad_pipeline','bad_address','bad_parameters','bad_local','bad_shared','bad_groups','bad_y','bad_threads','bad_stage','bad_error','bad_reserved']
rows=[]
for kind,items,prefix in [('manifest',modes,'command-ir-manifest-'),('regression',modes,'command-ir-manifest-regression-'),('threads',modes[:7]+['bad_threads'],'command-ir-aligned-threads-'),('legacy',['prepare','select','range','split','completed','copy','no_producer','no_selector'],'command-ir-manifest-legacy-bindings-')]:
 for mode in items:
  suffix='-02'if kind=='manifest'and mode=='bad_shared'else''
  target=ROOT/'results'/(prefix+mode.replace('_','-')+'-20261015'+suffix)
  v=verify_bindings(target,False)if kind=='legacy'else verify(target);assert v['status'].startswith('PASS')
  m=read(target/'execution/manifest.json');inp=read(target/'inputs.json');assert inp['static_library_SHA256']==libsha
  if kind in ['manifest','threads']:
   for run in read(target/'results.json')['runs']:
    for e in run['events']:
     if e['operation']=='executeCommandsInBuffer':
      ev=e['evidence'];assert ev['CPU_QMD_uploads_in_launch']==ev['CPU_constant_uploads_in_launch']==0
      for p in ev['owner_original_profiles']:assert p['constant_buffer_valid_mask']==6
  rows.append({'kind':kind,'mode':mode,'directory':str(target),'PID':m['pid'],'exact_uint32_words':v['exact_uint32_words'],'consumer_invocations':v.get('consumer_GPU_invocations_counted',v.get('GPU_invocations_counted')),'verification_receipt_SHA256':sha(target/'independent-verification.json')})
print('GTX oracles rechecked',len(rows),flush=True)
equal=0;native=[]
for kind,prefix,returned,source in [('manifest','command-ir-manifest-','command-ir-manifest-M1-return-20261015','gpu_command_frontend_general.metal'),('threads','command-ir-aligned-threads-','command-ir-aligned-threads-M1-return-20261015','gpu_command_frontend_threads.metal')]:
 ref=ROOT/'results'/returned/'Reference';nr=verify_m1(ref);assert nr['status']=='PASS';native.append(nr)
 assert sha(ref/'gpu_command_frontend_runtime.metal')==sha(ROOT/'src'/source)
 assert sha(ref/'cpu_icb_combined_shared.metal')==sha(ROOT/'src/cpu_icb_manifest.metal')
 for mode in modes[:7]:
  a=ROOT/'results'/(prefix+mode.replace('_','-')+'-20261015');b=ref/'results'/mode
  for x,y in zip(read(a/'results.json')['runs'],read(b/'results.json')['runs']):
   assert x['node_specs']==y['node_specs']
   for field in ['outputs','counter_files']:
    assert x[field]==y[field]
    for n in x[field]:assert(a/'outputs'/n).read_bytes()==(b/'outputs'/n).read_bytes();equal+=1
assert equal==600
control=read(ROOT/'results/command-ir-manifest-grid-control-20261015/independent-control-verification.json');assert control['status']=='PASS_EXPECTED_GRID_WITNESS_MISMATCH'and control['changed_uint32_words']==2085
grid=ROOT/'results/command-ir-manifest-grid-control-20261015';positive=ROOT/'results/command-ir-manifest-basic-20261015';gd=read(grid/'results.json');pd=read(positive/'results.json');gm=read(grid/'execution/manifest.json');gi=read(grid/'inputs.json')
assert gm['exit_code']==0 and not gm['SIGKILL_requested']and not gm['authoritative_ps_status']and gm['GPU_reservation']['state']=='terminal'
assert sha(grid/'application')==gi['executable_SHA256']==gm['original_binary_sha256']
for n,h in gi['source_hashes'].items():assert sha(grid/n)==h
for n,h in gi['assets_SHA256'].items():assert sha(grid/'assets'/n)==h
import struct
changed=0
for t,(r,p)in enumerate(zip(gd['runs'],pd['runs'])):
 assert r['command_status']==4 and r['node_specs']==p['node_specs'];spec=r['node_specs'][(t+1)%3];n=(1+0xa5a5a5a5%spec['groups'])*spec['local'];target=4+(t+2)%3
 for k,(name,cn)in enumerate(zip(r['outputs'],r['counter_files'])):
  expected=bytearray((positive/'outputs'/name).read_bytes())
  if k==target:
   for i in range(n):struct.pack_into('<I',expected,128+32*(k-4)+i*16+8,spec['groups']|(1<<16)|(1<<24))
   changed+=n
  assert(grid/'outputs'/name).read_bytes()==expected and(grid/'outputs'/cn).read_bytes()==(positive/'outputs'/cn).read_bytes()
assert changed==2085
primer=read(ROOT/'results/command-ir-manifest-final-primer-controls-20261015/verification.json');assert primer['status']=='PASS'and primer['checks']==60 and primer['library_SHA256']==libsha
system=read(ROOT/'results/command-ir-runtime-progress-20261015/system-and-source-check-final.json')
for f in system['system_files']:assert sha(f['path'])==f['SHA256']
assert sha('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist')==system['OCLP_SHA256']
(OUT/'system-check.json').write_text(json.dumps({'status':'PASS','system_files':system['system_files'],'OCLP_SHA256':system['OCLP_SHA256'],'system_files_unchanged':len(system['system_files'])},indent=2)+'\n')
paths=sorted(p for folder in ['src','tools']for p in(ROOT/folder).rglob('*')if p.is_file()and '__pycache__'not in p.parts)
snapshot={'files':[{'path':str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'SHA256':sha(p)}for p in paths]};(OUT/'source-snapshot.json').write_text(json.dumps(snapshot,indent=2)+'\n')
def total(kind,key):return sum(r[key]for r in rows if r['kind']==kind)
receipt={'status':'PASS','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'previous_goal_turn':'PROGRESS','current_goal_turn':'PROGRESS','objective_complete':False,'Git_branch':'main','Git_commit':None,'job_ids':[],'library_SHA256':libsha,'source_snapshot_SHA256':sha(OUT/'source-snapshot.json'),'materializer_SHA256':sha(ROOT/'results/command-ir-general-materializer-build-20261015-02/command_ir_materializer.metallib'),'manifest_trials':60,'manifest_exact_uint32_words':total('manifest','exact_uint32_words'),'manifest_consumer_invocations':total('manifest','consumer_invocations'),'aligned_threads_trials':24,'aligned_threads_exact_uint32_words':total('threads','exact_uint32_words'),'aligned_threads_consumer_invocations':total('threads','consumer_invocations'),'old_runtime_regression_trials':60,'old_runtime_regression_exact_uint32_words':total('regression','exact_uint32_words'),'legacy_bindings_trials':24,'legacy_bindings_exact_uint32_words':total('legacy','exact_uint32_words'),'M1_native_trials':42,'M1_GTX_output_counter_files_identical':equal,'inactive_CB0_control_checks':60,'stale_grid_control_trials':3,'stale_grid_expected_wrong_words':2085,'system_files_unchanged':len(system['system_files']),'OCLP_unchanged':True,'installed_driver_updated':False,'ordinary_applications_transparent':False,'integration_level':2,'performance_benchmark':False,'rows':rows,'BLOCKED':[],'NOT_RUN':['Full129-cohort regression on current library','General unregistered shader/resource layouts','Multidimensional and partial grids in GPU IR consumer','Stage-in and strides','Cross-context GPU copies and full concurrency','Transparent application integration','New-library performance benchmark','Video/display/power/full-VRAM qualification'],'next_action':'Broaden registered shader/resource layouts and multidimensional/partial-grid semantics, qualify full regression, then integrate an ordinary-API acceptance client; preserve independent NVIDIA driver-modernization branch.'}
(OUT/'qualification-receipt.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in receipt.items()if k not in ['rows','NOT_RUN']},ensure_ascii=False,indent=2))
