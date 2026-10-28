#!/usr/bin/env python3
"""Build an immutable combined application SDK; never install system files."""
from pathlib import Path
import argparse,datetime,hashlib,io,json,shutil,subprocess,tarfile
ROOT=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--reuse-library-from',type=Path);p.add_argument('--fp64-programs',type=Path);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();sdk=out/'KeplerMetalSDK';sdk.mkdir();commands=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(argv,label):
 r=subprocess.run(argv,capture_output=True,text=True,timeout=45);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':argv,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,r.returncode,flush=True);assert r.returncode==0,r.stderr[-3000:]
for n in ['src','include','lib','assets','examples','runtime']:(sdk/n).mkdir()
names=['KeplerCPUICB.h','KeplerCPUICB.mm','KeplerCommandIR.h','KeplerCommandIRPlan.inc','KeplerCommandIRScope.inc','KeplerNativeCommands.h','KeplerNativeCommands.mm','KeplerNativeRenderDraws.h','KeplerNativeRenderDraws.mm','KeplerNativeCAS.h','KeplerNativeCAS.mm','KeplerConditionalAux.h','KeplerNativeCASAdapter.inc','KeplerProgramImport.h']
for n in names:shutil.copyfile(ROOT/'src'/n,sdk/'src'/n)
fp64=None
if a.fp64_programs:
 source=a.fp64_programs.resolve();source.relative_to(ROOT/'results');fp64=json.loads((source/'summary.json').read_text());assert len(fp64['records']) in [15,24,60] and not fp64['GPU_execution']
 carrier=ROOT/'build/kepler_carrier.metallib';shutil.copyfile(carrier,sdk/'assets/fp64_carrier.metallib')
 pins=[];approved=[]
 for row in fp64['records']:
  info=row['info'];assert row['compiled'] and row['known_decode'] and info['strided_inputs'] and info['sm']==30 and 24<=info['registers']<=63 and not any(info[n] for n in ['scratch_bytes','crs_bytes','shared_bytes'])
  name=f"{row['operation']}-l{row['local']}";code=source/(name+'.sass');assert sha(code)==row['code_SHA256'] and code.stat().st_size==info['code_bytes'];shutil.copyfile(code,sdk/'assets'/('fp64_'+name+'.sass'))
  pins.append('{"%s","%s",%d,%d,%d}'%(name,row['code_SHA256'],row['local'],info['registers'],info['code_bytes']));approved.append(name)
 ops=['add','mul','fma','div','sqrt']+(['from_i64','from_u64','from_f32'] if len(fp64['records'])>=24 else [])+([f'to_{target}_{mode}' for target in ['f32','i64','u64'] for mode in ['rn','rz','rp','rm']] if len(fp64['records'])==60 else [])
 assert len(set(approved))==len(approved) and set(approved)=={f'{op}-l{local}' for op in ops for local in [32,128,1024]}
 generated='static const char KPFP64CarrierSHA[]="'+sha(carrier)+'";\nstatic const KPFP64Pin KPFP64Pins[]={\n'+',\n'.join(pins)+'\n};\n'
 (sdk/'src/KeplerFP64Programs.inc').write_text(generated)
 for n in ['KeplerFP64.h','KeplerFP64.mm']:shutil.copyfile(ROOT/'src'/n,sdk/'src'/n)
 names+=['KeplerFP64.h','KeplerFP64.mm','KeplerFP64Programs.inc'];shutil.copyfile(ROOT/'src/KeplerFP64.h',sdk/'include/KeplerFP64.h')
 (sdk/'assets/fp64_manifest.json').write_text(json.dumps({'compiler_source_SHA256':fp64['compiler_source_SHA256'],'carrier_SHA256':sha(carrier),'programs':fp64['records'],'runtime_metadata_from_build_pins':True,'GPU_qualification_pending':True},indent=2)+'\n')
for n in ['KeplerCPUICB.h','KeplerNativeCAS.h']:shutil.copyfile(sdk/'src'/n,sdk/'include'/n)
for n in ['README.md','examples/client.mm','examples/build_example.py','examples/run_example.py','examples/verify_example.py']:shutil.copyfile(ROOT/'sdk-combined'/n,sdk/n)
for n in ['literal_client.mm','build_literal_client.py','run_literal_client.py','verify_literal_client.py']:shutil.copyfile(ROOT/'sdk-combined/examples'/n,sdk/'examples'/n)
for n in ['cpu_icb_gpu_copy_client.mm','build_cpu_icb_gpu_copy_client.py','cpu_icb_copy_graph_client.mm','build_cpu_icb_copy_graph_client.py','cpu_icb_copy_mixed_client.mm','build_cpu_icb_copy_mixed_client.py','cpu_icb_copy_refusal_client.mm','build_cpu_icb_copy_refusal_client.py','cpu_icb_copy_async_client.mm','build_cpu_icb_copy_async_client.py','cpu_icb_registered_copy_client.mm','build_cpu_icb_registered_copy_client.py','cpu_icb_registered_bounds_client.mm','build_cpu_icb_registered_bounds_client.py','cpu_icb_dynamic_copy_client.mm','build_cpu_icb_dynamic_copy_client.py','cpu_icb_dynamic_bounds_client.mm','build_cpu_icb_dynamic_bounds_client.py','cpu_icb_combined_shared_copy_client.mm','build_cpu_icb_combined_shared_copy_client.py','cpu_icb_combined_shared_bounds_client.mm','build_cpu_icb_combined_shared_bounds_client.py','gpu_command_selection_client.mm','build_gpu_command_selection_client.py','gpu_command_selection_refusals_client.mm','build_gpu_command_selection_refusals_client.py','gpu_command_geometry_client.mm','build_gpu_command_geometry_client.py','gpu_command_geometry_refusals_client.mm','build_gpu_command_geometry_refusals_client.py','gpu_command_bindings_client.mm','build_gpu_command_bindings_client.py','gpu_command_bindings_refusals_client.mm','build_gpu_command_bindings_refusals_client.py']:shutil.copyfile(ROOT/'sdk-combined/examples'/n,sdk/'examples'/n)
for n in ['run_resident_qmd_copy.py','run_registered_resident_copy.py','verify_cpu_icb_gpu_copy.py','verify_cpu_icb_copy_graph.py','verify_cpu_icb_copy_mixed.py','verify_cpu_icb_copy_refusals.py','verify_cpu_icb_copy_async.py','verify_registered_resident_copy.py','verify_registered_resident_bounds.py','run_dynamic_resident_copy.py','verify_dynamic_resident_copy.py','verify_dynamic_resident_bounds.py','run_combined_shared_copy.py','verify_combined_shared_copy.py','verify_combined_shared_bounds.py','run_gpu_command_selection.py','verify_gpu_command_selection.py','verify_gpu_selection_refusals.py','run_gpu_command_geometry.py','verify_gpu_command_geometry.py','verify_gpu_geometry_refusals.py','run_gpu_command_bindings.py','verify_gpu_command_bindings.py','verify_gpu_bindings_refusals.py']:shutil.copyfile(ROOT/'tools'/n,sdk/'examples'/n)
copy_library=ROOT/'results/resident-qmd-public-copy-build-20261014-03/library.metallib'
assert sha(copy_library)=='913c4c1a32db704bc0ee5e54c6d9084f8601418c924fbd35ef72bcc08cb64ecd';shutil.copyfile(copy_library,sdk/'assets/gpu_copy_integer.metallib')
if fp64:
 for n in ['fp64_client.mm','build_fp64_client.py','run_fp64_client.py','verify_fp64_client.py']:shutil.copyfile(ROOT/'sdk-combined/examples'/n,sdk/'examples'/n)
 shutil.copyfile(ROOT/'tools/verify_fp64_math.py',sdk/'examples/fp64_cpu_oracle.py')
 if len(fp64['records'])>=24:
  for n in ['fp64_conversion_client.mm','build_fp64_conversion_client.py','verify_fp64_conversion_client.py']:shutil.copyfile(ROOT/'sdk-combined/examples'/n,sdk/'examples'/n)
  shutil.copyfile(ROOT/'tools/fp64_conversion_inputs.py',sdk/'examples/fp64_conversion_inputs.py')
 if len(fp64['records'])==60:
  for n in ['fp64_reverse_client.mm','build_fp64_reverse_client.py','verify_fp64_reverse_client.py']:shutil.copyfile(ROOT/'sdk-combined/examples'/n,sdk/'examples'/n)
  shutil.copyfile(ROOT/'tools/fp64_reverse_inputs.py',sdk/'examples/fp64_reverse_inputs.py')
shutil.copyfile(ROOT/'tools/lab_gpu_reservation.py',sdk/'runtime/lab_gpu_reservation.py')
shutil.copyfile(ROOT/'sdk-combined/runtime/run_sdk_host.py',sdk/'runtime/run_sdk_host.py')
objects=[];reused=None;archive=sdk/'lib/libKeplerMetal.a'
if a.reuse_library_from:
 old=a.reuse_library_from.resolve();old.relative_to(ROOT/'results');reused=json.loads((old/'BUILD_MANIFEST.json').read_text())
 assert reused['architecture']=='x86_64' and reused['SDK']==subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-version'],text=True).strip() and reused['clang']==subprocess.check_output(['clang++','--version'],text=True)
 for n in names:assert sha(sdk/'src'/n)==reused['source_SHA256'][n]
 assert sha(old/'lib/libKeplerMetal.a')==reused['static_library_SHA256'];shutil.copyfile(old/'lib/libKeplerMetal.a',archive);assert sha(archive)==reused['static_library_SHA256']
else:
 for n in ['KeplerCPUICB','KeplerNativeCommands','KeplerNativeRenderDraws','KeplerNativeCAS']+(['KeplerFP64'] if fp64 else []):
  obj=out/(n+'.o');run(['clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc' if n=='KeplerNativeCAS' else '-fobjc-arc','-I',str(sdk/'src'),'-c',str(sdk/'src'/(n+'.mm')),'-o',str(obj)],'compile-'+n);objects.append(obj)
 run(['ar','rcs',str(archive),*[str(p) for p in objects]],'archive')
for f in (ROOT/'results/native-cas-sdk-build-20261014-02/KeplerNativeCAS/assets').iterdir():shutil.copyfile(f,sdk/'assets'/f.name)
shutil.copyfile(ROOT/'src/cpu_icb_native_cas_manifest.json',sdk/'assets/cpu_icb_native_cas_manifest.json')
for d,n in [('render-state-final','render_state_carrier.metallib'),('gpu-argument-selector-passive','gpu_argument_selector.metallib')]:shutil.copyfile(ROOT/'results'/d/n,sdk/'assets'/n)
shutil.copyfile(ROOT/'results/native-literal-bank-passive-20261014/literal_lut.metallib',sdk/'assets/literal_lut.metallib')
for n in ['cpu_icb_literal_lut_manifest.json','cpu_icb_literal_lut_values.json']:shutil.copyfile(ROOT/'src'/n,sdk/'assets'/n)
dynamic_library=ROOT/'results/cpu-icb-manifest-gpu-qualified/cpu_icb_manifest.metallib'
assert sha(dynamic_library)=='ed7854542c2a45533f0114fd7e1100f31f52728433f83667b5d9cd54568cea94';shutil.copyfile(dynamic_library,sdk/'assets/dynamic_profiles.metallib')
shutil.copyfile(ROOT/'src/cpu_icb_dynamic_resident_manifest.json',sdk/'assets/cpu_icb_dynamic_resident_manifest.json')
combined_library=ROOT/'results/resident-combined-shared-passive-20261014/combined_shared.metallib'
assert sha(combined_library)=='b66637d429769478b5be034572e258f16078760ab511f016aec5a57fc76fdebd';shutil.copyfile(combined_library,sdk/'assets/combined_shared.metallib')
shutil.copyfile(ROOT/'src/cpu_icb_combined_shared_manifest.json',sdk/'assets/cpu_icb_combined_shared_manifest.json')
selector_library=ROOT/'results/gpu-generated-selector-build-20261014/gpu_command_selector.metallib'
assert sha(selector_library)=='b6d3f29fc4f85dd020f96fff3fc5f2586548aad483ea2649172b56545a9e581c';shutil.copyfile(selector_library,sdk/'assets/gpu_command_selector.metallib')
geometry_library=ROOT/'results/gpu-generated-geometry-shader-build-20261014-02/gpu_command_geometry.metallib'
assert sha(geometry_library)=='f6cc04a4c2555a2555dc06a2f02687ffe5a63fb5304619b1d9662ec1f0176441';shutil.copyfile(geometry_library,sdk/'assets/gpu_command_geometry.metallib')
bindings_library=ROOT/'results/gpu-generated-bindings-shader-build-20261014-03/gpu_command_bindings.metallib'
assert sha(bindings_library)=='ce99cdc66f55f4ce7069b9518ed1f074feea2bee6daded2d320098e29b43f290';shutil.copyfile(bindings_library,sdk/'assets/gpu_command_bindings.metallib')
build={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'Git_branch':'main','Git_commit':None,'architecture':'x86_64','macOS':subprocess.check_output(['sw_vers'],text=True),'SDK':subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-version'],text=True).strip(),'clang':subprocess.check_output(['clang++','--version'],text=True),'source_SHA256':{n:sha(sdk/'src'/n) for n in names},'object_SHA256':{p.name:sha(p) for p in objects},'static_library_SHA256':sha(archive),'commands':commands,'system_modified':False,'Qwen_job_ids':[]}
build.update(explicit_library_reuse_from=str(a.reuse_library_from) if a.reuse_library_from else None,reused_build_provenance=reused)
(sdk/'BUILD_MANIFEST.json').write_text(json.dumps(build,indent=2)+'\n');(sdk/'qualification.json').write_text(json.dumps({'client_GPU_qualification_pending':True,'experimental':True,'native_CB0_sizes':[256,512,1024],'ordinary_applications_transparent':False,'all_hardware_functions_supported':False,'GPU_generated_ICB':False,'performance_benchmark':False,'system_modified':False,'Qwen_job_ids':[]},indent=2)+'\n')
files=sorted(x for x in sdk.rglob('*') if x.is_file());entries=[{'path':str(f.relative_to(sdk)),'bytes':f.stat().st_size,'SHA256':sha(f)} for f in files];(sdk/'FILE_MANIFEST.json').write_text(json.dumps({'files':entries,'scope':'Explicit adapted application SDK, not a driver installer'},indent=2)+'\n')
tar=out/('KeplerMetalSDK-combined-cb0-fp64-x86_64-2026-10-14.tar.gz' if fp64 else 'KeplerMetalSDK-combined-cb0-x86_64-2026-10-14.tar.gz')
with tarfile.open(tar,'x:gz') as t:
 for f in sorted(x for x in sdk.rglob('*') if x.is_file()):raw=f.read_bytes();i=tarfile.TarInfo('KeplerMetalSDK/'+str(f.relative_to(sdk)));i.mode=0o644;i.size=len(raw);i.mtime=0;t.addfile(i,io.BytesIO(raw))
with tarfile.open(tar) as t:
 for e in entries:raw=t.extractfile('KeplerMetalSDK/'+e['path']).read();assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['SHA256']
delivery={'path':str(tar),'SHA256':sha(tar),'static_library_SHA256':sha(archive),'files':len(entries)+1,'all_SHA_verified':True,'client_GPU_qualification_pending':True};(out/'delivery.json').write_text(json.dumps(delivery,indent=2)+'\n');print(json.dumps(delivery,indent=2))
