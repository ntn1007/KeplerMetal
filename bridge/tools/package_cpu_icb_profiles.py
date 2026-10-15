#!/usr/bin/env python3
"""Package immutable source/raw evidence; refuse credentials and host binaries."""
from pathlib import Path
import argparse,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1];LAB=ROOT.parent
p=argparse.ArgumentParser();p.add_argument('--name',default='KEPLERMETAL_CPU_ICB_PIPELINES_2026-10-13.zip');a=p.parse_args();archive=ROOT/a.name
assert Path(a.name).name==a.name and a.name.endswith('.zip') and not archive.exists()
cohorts=['native-pipeline-profiles-captured','native-pipeline-profiles-vector-captured','cpu-icb-registered-legacy-prepared','cpu-icb-registered-legacy-gpu-qualified','cpu-icb-profiles-prepared','cpu-icb-profiles-label-descriptor-prepared','cpu-icb-profiles-reflection-access-prepared','cpu-icb-profiles-gpu-qualified','cpu-icb-profiles-lifetime-prepared','cpu-icb-profiles-lifetime-private-buffers-prepared','cpu-icb-profiles-lifetime-gpu-qualified','cpu-icb-profiles-progress','pipeline-profile-references']
files=set()
for cohort in cohorts:files.update(x for x in (ROOT/'results'/cohort).rglob('*') if x.is_file() and not x.is_symlink())
for name in ['CPU_ICB_PIPELINES_NATIFS.txt','results/hardware-coverage.json','results/indirect-compute-native-qualified/indirect_compute_probe.metallib','src/KeplerCPUICB.h','src/KeplerCPUICB.mm','src/KeplerNativeCommands.h','src/KeplerNativeCommands.mm','src/cpu_icb_profiles.metal','tools/cpu_icb_profiles_probe.mm','tools/cpu_icb_profiles_lifetime_probe.mm','tools/native_pipeline_profiles_probe.mm','tools/reproduce_cpu_icb_profiles.py','tools/reproduce_cpu_icb_profiles_lifetime.py','tools/reproduce_native_pipeline_profiles.py','tools/verify_cpu_icb_profiles.py','tools/verify_cpu_icb_profiles_lifetime.py','tools/verify_cpu_icb.py','tools/reproduce_cpu_icb.py','tools/cpu_icb_probe.mm','tools/decode_native_commands.py','tools/make_cpu_icb_profiles_report.py','tools/package_cpu_icb_profiles.py','tools/verify_cpu_icb_profiles_delivery.py','tools/run_signed_probe.py']:files.add(ROOT/name)
research=LAB/'driver-research-2026-10-13'
for name in ['reports/STRATEGIE_KEPLERMETAL.txt','reports/STRATEGIE_PREUVES.json','reports/MODERNISATION_NVIDIA_ACTUALISEE.json','reports/MODERNISATION_NVIDIA_ACTUALISEE.csv','reports/METAL_CAPACITES_ACTUALISEES.json','reports/METAL_CAPACITES_ACTUALISEES.csv','reports/EXPERIMENTATIONS_PRIORISEES.json','tools/make_strategy_report.py']:files.add(research/name)
magic={b'\xcf\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xce\xfa\xed\xfe',b'\xfe\xed\xfa\xce',b'\xca\xfe\xba\xbe',b'\x7fELF'};selected=[];excluded=[]
for f in sorted(files):
 assert f.is_file() and not f.is_symlink();rel=str(f.relative_to(LAB))
 if '__pycache__' in f.parts or f.suffix in ('.o','.a','.dylib') or f.read_bytes()[:4] in magic or f.name=='packet-delivery.json':excluded.append(rel);continue
 assert not f.name.startswith('.env') and f.name not in ('config.toml','id_rsa','id_ed25519','coordinator.token') and 'qwen-private' not in f.parts
 selected.append(f)
entries=[{'path':str(f.relative_to(LAB)),'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in selected]
manifest={'files':entries,'excluded_host_binaries_and_caches':excluded,'integration_level':1,'ICB_contract_complete':False,'GPU_resident_ICB_indirection':False,'all_hardware_functions_supported':False,'system_modified':False,'Qwen_job_ids':[],'scope':'Incremental source/raw evidence; not an installable driver. Portable verification does not re-attest omitted host executables or repeat GPU execution.'}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for f,e in zip(selected,entries):
  raw=f.read_bytes();assert hashlib.sha256(raw).hexdigest()==e['sha256'];z.writestr(e['path'],raw)
 z.writestr('PACKET_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for e in entries:
  raw=z.read(e['path']);assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['sha256']
delivery={'path':str(archive),'bytes':archive.stat().st_size,'content_files':len(entries),'SHA256':hashlib.sha256(archive.read_bytes()).hexdigest(),'CRC_and_all_SHA256_verified':True,'Qwen_job_ids':[]}
(ROOT/'results/cpu-icb-profiles-progress/packet-delivery.json').write_text(json.dumps(delivery,indent=2)+'\n');print(json.dumps(delivery,indent=2))
