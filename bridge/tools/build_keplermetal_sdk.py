#!/usr/bin/env python3
"""Build a local static SDK and immutable archive; no installation actions."""
from pathlib import Path
import argparse,datetime,hashlib,io,json,shutil,subprocess,tarfile
ROOT=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--reuse-library',type=Path);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();sdk=out/'KeplerMetalSDK';sdk.mkdir();commands=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(argv,label):
 r=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':argv,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,r.returncode,flush=True);assert r.returncode==0,r.stderr[-2000:]
for n in ['include','lib','src','assets','examples']:(sdk/n).mkdir()
sources=[]
for n in ['KeplerCPUICB.h','KeplerCPUICB.mm','KeplerNativeCommands.h','KeplerNativeCommands.mm','KeplerNativeRenderDraws.h','KeplerNativeRenderDraws.mm']:
 f=sdk/'src'/n;f.write_bytes((ROOT/'src'/n).read_bytes());sources.append(f)
shutil.copyfile(sdk/'src/KeplerCPUICB.h',sdk/'include/KeplerCPUICB.h')
for n in ['README.md','examples/client.mm','examples/client.metal','examples/build_example.py','examples/run_example.py','examples/verify_example.py']:shutil.copyfile(ROOT/'sdk'/n,sdk/n)
objects=[]
static=sdk/'lib/libKeplerMetal.a';reused=None
if a.reuse_library:
 old=a.reuse_library.resolve();reused=json.loads((old.parents[1]/'BUILD_MANIFEST.json').read_text());assert sha(old)==reused['static_archive_SHA256']
 for f in sources:assert sha(f)==reused['source_SHA256'][str(f.relative_to(sdk))]
 shutil.copyfile(old,static)
else:
 for n in ['KeplerCPUICB','KeplerNativeCommands','KeplerNativeRenderDraws']:
  obj=out/(n+'.o');run(['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',str(sdk/'src'),'-c',str(sdk/'src'/(n+'.mm')),'-o',str(obj)],'compile-'+n);objects.append(obj)
 run(['ar','rcs',str(static),*[str(x) for x in objects]],'archive')
for directory,n in [('render-state-final','render_state_carrier.metallib'),('gpu-argument-selector-passive','gpu_argument_selector.metallib')]:shutil.copyfile(ROOT/'results'/directory/n,sdk/'assets'/n)
qualification={'experimental':True,'integration':'Explicit application adaptation; SDK client qualification pending','ordinary_applications_transparent':False,'full_hardware_coverage':False,'system_modified':False,'hardware_profile':{'registry_id':4294968458,'GPU':'GTX 880M/GK104/SM30/8GiB','driver_SHA256':'2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054'},'qualified_targets':{'formats':[70,80,115,125],'sizes':[[64,48],[96,64],[128,96]],'samples':1,'MRT':False},'qualified_scope':'Refer to the existing pinned feature reports; registration is not GPU qualification','GPU_resident_ICB':False,'GPU_generated_ICB':False,'performance_benchmark':False,'client_Private_result_writes_forbidden':True,'Qwen_job_ids':[]};(sdk/'qualification.json').write_text(json.dumps(qualification,indent=2)+'\n')
build={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'Git_branch':'main','Git_commit':None,'architecture':'x86_64','macOS':subprocess.check_output(['sw_vers'],text=True),'SDK':subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-version'],text=True).strip(),'clang':subprocess.check_output(['clang++','--version'],text=True),'source_SHA256':{str(f.relative_to(sdk)):sha(f) for f in sources},'object_SHA256':{f.name:sha(f) for f in objects},'static_archive_SHA256':sha(static),'commands':commands,'system_modified':False,'Qwen_job_ids':[],'library_reused_from':str(a.reuse_library) if a.reuse_library else None,'reused_build_provenance':reused};(sdk/'BUILD_MANIFEST.json').write_text(json.dumps(build,indent=2)+'\n')
files=sorted(f for f in sdk.rglob('*') if f.is_file());entries=[{'path':str(f.relative_to(sdk)),'bytes':f.stat().st_size,'SHA256':sha(f)} for f in files];manifest={'files':entries,'scope':'Prebuilt experimental application SDK, not a system driver installer','secrets_excluded':True};(sdk/'FILE_MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
archive=out/'KeplerMetalSDK-x86_64-2026-10-14.tar.gz'
with tarfile.open(archive,'x:gz') as t:
 for f in sorted(f for f in sdk.rglob('*') if f.is_file()):b=f.read_bytes();info=tarfile.TarInfo('KeplerMetalSDK/'+str(f.relative_to(sdk)));info.size=len(b);info.mode=0o644;info.mtime=0;t.addfile(info,io.BytesIO(b))
with tarfile.open(archive) as t:
 for e in entries:raw=t.extractfile('KeplerMetalSDK/'+e['path']).read();assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['SHA256']
delivery={'path':str(archive),'SHA256':sha(archive),'static_archive_SHA256':sha(static),'files':len(entries)+1,'all_fingerprints_verified':True,'system_modified':False,'client_GPU_qualification':False};(out/'delivery.json').write_text(json.dumps(delivery,indent=2)+'\n');print(json.dumps(delivery,indent=2))
