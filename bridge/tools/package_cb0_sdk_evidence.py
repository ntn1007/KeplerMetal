#!/usr/bin/env python3
"""Freeze delivered SDK plus public-client evidence and verify six raw oracles."""
from pathlib import Path
import hashlib,importlib.util,json,zipfile
ROOT=Path(__file__).resolve().parents[1];LAB=ROOT.parent
archive=ROOT/'KEPLERMETAL_SDK_CB0_APPLICATION_ADAPTEE_2026-10-14.zip';check=ROOT/'results/combined-cb0-sdk-portable-verification';assert not archive.exists() and not check.exists()
files=set()
for folder in (ROOT/'results').glob('combined-cb0-sdk-*'):
 files.update(p for p in folder.rglob('*') if p.is_file())
files.update(p for p in (ROOT/'sdk-combined').rglob('*') if p.is_file())
files.update(ROOT/n for n in ['SDK_CB0_APPLICATION_ADAPTEE.txt','results/hardware-coverage.json','tools/build_combined_keplermetal_sdk.py','tools/make_cb0_sdk_report.py','tools/package_cb0_sdk_evidence.py','tools/lab_gpu_reservation.py'])
for name in ['KeplerCPUICB.h','KeplerCPUICB.mm','KeplerNativeCommands.h','KeplerNativeCommands.mm','KeplerNativeRenderDraws.h','KeplerNativeRenderDraws.mm','KeplerNativeCAS.h','KeplerNativeCAS.mm','KeplerNativeCASAdapter.inc','KeplerProgramImport.h']:files.add(ROOT/'src'/name)
magic={b'\xcf\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xce\xfa\xed\xfe',b'\xfe\xed\xfa\xce',b'\xca\xfe\xba\xbe',b'\xbe\xba\xfe\xca',b'\x7fELF'};selected=[];excluded=[]
for p in sorted(files):
 assert p.is_file() and not p.is_symlink();assert p.name not in ['coordinator.token','config.toml','id_rsa','id_ed25519'] and not p.name.startswith('.env') and 'qwen-private' not in p.parts
 raw=p.read_bytes();rel=str(p.relative_to(LAB))
 if '__pycache__' in p.parts or p.suffix in ['.o','.a','.dylib'] or raw[:4] in magic or p.name=='packet-delivery.json':excluded.append(rel);continue
 selected.append((rel,raw))
entries=[{'path':n,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for n,raw in selected]
manifest={'files':entries,'excluded_host_binaries_and_caches':excluded,'scope':'Delivered tar explicitly contains the static library. Evidence omits mapped host executables. Portable checks re-evaluate raw outputs only, without GPU execution or executable re-attestation.','integration_level':2,'ordinary_applications_transparent':False,'all_hardware_supported':False,'system_modified':False,'Qwen_job_ids':[]}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
 for n,raw in selected:z.writestr(n,raw)
 z.writestr('PACKET_MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for e in entries:
  raw=z.read(e['path']);assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['sha256']
 check.mkdir();z.extractall(check)
sdk=check/'bridge/results/combined-cb0-sdk-extracted-client-20261014-03/KeplerMetalSDK';results={}
for kind,verifier in [('literal','verify_literal_client.py'),('cas','verify_example.py')]:
 spec=importlib.util.spec_from_file_location(kind,sdk/'examples'/verifier);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 for mode in ['prepared','gpu','native']:
  name=f'combined-cb0-sdk-{kind}-{mode}-20261014-03';v=module.verify(check/'bridge/results'/name,portable=True);assert v['status']=='PASS';results[name]={k:value for k,value in v.items() if k!='raw_SHA256'}
(check/'verification.json').write_text(json.dumps(results,indent=2)+'\n')
delivery={'path':str(archive),'files':len(entries),'SHA256':hashlib.sha256(archive.read_bytes()).hexdigest(),'all_CRC_SHA_verified':True,'portable_oracles':len(results),'fresh_GPU_execution':False}
(ROOT/'results/combined-cb0-sdk-progress/packet-delivery.json').write_text(json.dumps(delivery,indent=2)+'\n');print(json.dumps(delivery,indent=2))
