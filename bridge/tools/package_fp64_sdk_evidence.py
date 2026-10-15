#!/usr/bin/env python3
"""Freeze the SDK and client captures; recalculate11oracles after extraction."""
from pathlib import Path
import hashlib,importlib.util,json,sys,zipfile
ROOT=Path(__file__).resolve().parents[1];LAB=ROOT.parent
archive=ROOT/'KEPLERMETAL_SDK_FP64_2026-10-14.zip';check=ROOT/'results/combined-fp64-sdk-portable-verification-20261014';assert not archive.exists() and not check.exists()
files=set()
for folder in (ROOT/'results').glob('combined-fp64-sdk-*'):
 files.update(p for p in folder.rglob('*') if p.is_file())
files.update(p for p in (ROOT/'results/fp64-sdk-strided-offline-20261014').rglob('*') if p.is_file())
files.update(p for p in (ROOT/'sdk-combined').rglob('*') if p.is_file())
for n in ['KeplerCPUICB.h','KeplerCPUICB.mm','KeplerNativeCommands.h','KeplerNativeCommands.mm','KeplerNativeRenderDraws.h','KeplerNativeRenderDraws.mm','KeplerNativeCAS.h','KeplerNativeCAS.mm','KeplerNativeCASAdapter.inc','KeplerProgramImport.h','KeplerFP64.h','KeplerFP64.mm']:files.add(ROOT/'src'/n)
for n in ['build_combined_keplermetal_sdk.py','fp64_math_compile.c','build_fp64_math.py','make_fp64_sdk_report.py','package_fp64_sdk_evidence.py','lab_gpu_reservation.py']:files.add(ROOT/'tools'/n)
files.update(ROOT/n for n in ['SDK_FP64_APPLICATION_ADAPTEE_2026-10-14.txt','results/hardware-coverage.json'])
magic={b'\xcf\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xce\xfa\xed\xfe',b'\xfe\xed\xfa\xce',b'\xca\xfe\xba\xbe',b'\xbe\xba\xfe\xca',b'\x7fELF'}
selected=[];excluded=[]
for p in sorted(files):
 assert p.is_file() and not p.is_symlink() and p.name not in ['coordinator.token','config.toml','id_rsa','id_ed25519'] and not p.name.startswith('.env') and 'qwen-private' not in p.parts
 raw=p.read_bytes();relative=str(p.relative_to(LAB))
 if '__pycache__' in p.parts or p.suffix in ['.o','.a','.dylib'] or raw[:4] in magic or p.name=='packet-delivery.json':excluded.append(relative);continue
 selected.append((relative,raw))
entries=[{'path':n,'bytes':len(raw),'SHA256':hashlib.sha256(raw).hexdigest()} for n,raw in selected]
manifest={'files':entries,'excluded_host_binaries_and_caches':excluded,'Git_branch':'main','Git_commit':None,'integration_level':2,'ordinary_applications_transparent':False,'all_hardware_supported':False,'system_modified':False,'Qwen_job_ids':[],'scope':'Delivered tar contains exact static library. Evidence omits mapped host binaries. Portable raw checks are not new GPU execution.'}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
 for n,raw in selected:z.writestr(n,raw)
 z.writestr('PACKET_MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for e in entries:
  raw=z.read(e['path']);assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['SHA256']
 check.mkdir();z.extractall(check)
sdk=check/'bridge/results/combined-fp64-sdk-extracted-client-20261014-02/KeplerMetalSDK';sys.path.insert(0,str(sdk/'examples'))
groups={'fp64':(['combined-fp64-sdk-small-prepared-20261014-02','combined-fp64-sdk-small-gpu-20261014-02','combined-fp64-sdk-prepared-20261014-02','combined-fp64-sdk-gpu-20261014-02','combined-fp64-sdk-no-producer-20261014-02'],'verify_fp64_client.py'),
        'cas':([f'combined-fp64-sdk-cas-{m}-20261014-02' for m in ['prepared','gpu','native']],'verify_example.py'),
        'literal':([f'combined-fp64-sdk-literal-{m}-20261014-02' for m in ['prepared','gpu','native']],'verify_literal_client.py')}
verified={}
for kind,(names,n) in groups.items():
 spec=importlib.util.spec_from_file_location('portable_'+kind,sdk/'examples'/n);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 for name in names:
  v=module.verify(check/'bridge/results'/name,portable=True);assert v['status'].startswith('PASS');verified[name]={k:x for k,x in v.items() if k not in ['raw_SHA256','raw_SHA256_files']}
(check/'verification.json').write_text(json.dumps(verified,indent=2)+'\n')
delivery={'path':str(archive),'SHA256':hashlib.sha256(archive.read_bytes()).hexdigest(),'files':len(entries),'bytes':archive.stat().st_size,'all_CRC_SHA_verified':True,'portable_oracles':len(verified),'all_portable_oracles_PASS':True,'fresh_GPU_execution_by_packager':False,'goal_complete':False,'Qwen_job_ids':[]}
assert len(verified)==11
(ROOT/'results/combined-fp64-sdk-progress-20261014/packet-delivery.json').write_text(json.dumps(delivery,indent=2)+'\n');print(json.dumps(delivery,indent=2))
