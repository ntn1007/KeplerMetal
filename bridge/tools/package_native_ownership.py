#!/usr/bin/env python3
"""Incremental, verified source/evidence packet; no old archive overwritten."""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1];LAB=ROOT.parent;out=ROOT/'KEPLERMETAL_METADATA_RESSOURCES_2026-10-13.zip';assert not out.exists();files=set()
cohorts=['driver-runtime-layout','native-command-capture','native-command-relocation-capture','native-metadata-count-normalized','native-resource-ownership','native-command-ownership','native-retention-observed','indirect-descriptor-gpu-readback','native-stream-progress','native-ownership-progress']
for name in cohorts:files.update(p for p in (ROOT/'results'/name).rglob('*') if p.is_file() and not p.is_symlink())
names=['analyze_native_launches.py','decode_native_commands.py','driver_runtime_layout.mm','native_command_capture.mm','reproduce_native_metadata_count.py','verify_native_metadata_count.py','make_native_stream_report.py','native_resource_ownership.mm','reproduce_native_resource_ownership.py','native_retention_probe.mm','reproduce_native_retention.py','objc_type_layout.py','verify_native_ownership.py','reproduce_indirect_descriptor_readback.py','verify_indirect_descriptor_readback.py','make_native_ownership_report.py','package_native_ownership.py','run_signed_probe.py','indirect_compute_probe.mm','verify_native_command_relocations.py','recognize_native_cas.py','metallib_air.py']
files.update(ROOT/'tools'/name for name in names)
files.update(ROOT/path for path in ['RESSOURCES_COMMANDES_NVIDIA.txt','METADATA_COMMAND_STREAM.txt','results/hardware-coverage.json','src/KeplerProgramImport.h','src/indirect_compute_probe.metal'])
for rel in ['reports/STRATEGIE_KEPLERMETAL.txt','reports/STRATEGIE_PREUVES.json','reports/STRATEGIE_LIVRAISON.json','reports/MODERNISATION_NVIDIA_ACTUALISEE.json','reports/MODERNISATION_NVIDIA_ACTUALISEE.csv','reports/METAL_CAPACITES_ACTUALISEES.json','reports/METAL_CAPACITES_ACTUALISEES.csv','reports/EXPERIMENTATIONS_PRIORISEES.json','tools/make_strategy_report.py']:files.add(LAB/'driver-research-2026-10-13'/rel)
envy=ROOT/'vendor/envytools-f102b82381f3f11cee113d16374c87091db039d9'
for rel in ['rnndb/graph/gk104_compute.xml','rnndb/graph/gk104_p2mf.xml','rnndb/copyright.xml','demmt/pushbuf.c','COPYING']:
 p=envy/rel
 if p.exists():files.add(p)
mesa=next((ROOT/'vendor').glob('mesa*/src/gallium/drivers/nouveau/nvc0/nve4_compute.c'));files.add(mesa)
selected=[];excluded=[];native={b'\xcf\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xce\xfa\xed\xfe',b'\xfe\xed\xfa\xce',b'\xca\xfe\xba\xbe',b'\x7fELF'}
for p in sorted(files):
 rel=str(p.relative_to(LAB));assert p.is_file() and not p.is_symlink()
 with p.open('rb') as f:magic=f.read(4)
 if '__pycache__' in p.parts or p.suffix in ['.o','.a','.dylib'] or magic in native or p.name in ['packet-delivery.json','instruction-count-consumer.asm']:
  excluded.append(rel);continue
 if p.name.startswith('.env') or p.name in ['config.toml','id_rsa','id_ed25519'] or 'coordinator.token' in p.name:raise SystemExit('Credential/config candidate refused')
 selected.append(p)
entries=[{'path':str(p.relative_to(LAB)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in selected]
manifest={'files':entries,'excluded_host_binaries_caches_and_unbounded_disassembly':excluded,'Qwen_job_ids':[],'system_modifications':False,'all_hardware_functions_supported':False,'ICB_implemented':False,'captured_GPU_readbacks':True,'scope':'Incremental metadata/ownership/native GPU descriptor evidence. Existing pinned workspace and Apple toolchain required to rerun GPU probes; Python raw readback verifier is portable after extraction. Not a driver to install.'}
with zipfile.ZipFile(out,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p,entry in zip(selected,entries):
  data=p.read_bytes();assert hashlib.sha256(data).hexdigest()==entry['sha256'];z.writestr(entry['path'],data)
 z.writestr('PACKET_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
with zipfile.ZipFile(out) as z:
 assert z.testzip() is None and len(z.namelist())==len(entries)+1
 for entry in entries:
  data=z.read(entry['path']);assert len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256']
delivery={'path':str(out),'bytes':out.stat().st_size,'content_files':len(entries),'ZIP_entries':len(entries)+1,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'CRC_and_all_SHA256_verified':True,'Qwen_job_ids':[]}
(ROOT/'results/native-ownership-progress/packet-delivery.json').write_text(json.dumps(delivery,indent=2)+'\n');print(json.dumps(delivery,indent=2))
