#!/usr/bin/env python3
"""Incremental source/raw-evidence packet; previous packets remain unchanged."""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1];LAB=ROOT.parent;out=ROOT/'KEPLERMETAL_METALLIB_TRANSPORT_2026-10-13.zip';assert not out.exists();files=set()
cohorts=['metallib-native-preservation','metallib-planner-positive','metallib-planner-semantic-control','metallib-liveness-recheck','metallib-liveness-final','native-cas-clobber-rejection',
         'indirect-transport-audit','indirect-compute-native','indirect-compute-native-corrected','indirect-compute-native-qualified','metallib-transport-progress']
for name in cohorts:files.update(p for p in (ROOT/'results'/name).rglob('*') if p.is_file() and not p.is_symlink())
for rel in ['METALLIB_TRANSPORT_NATIF.txt','results/hardware-coverage.json','tools/metallib_air.py','tools/metallib_air_dump.c','tools/recognize_native_cas.py',
            'tools/plan_native_metallib_repair.py','tools/reproduce_metallib_native_repair.py','tools/verify_metallib_native_repair.py','tools/air_cas_probe.mm',
            'tools/reproduce_indirect_transport_audit.py','tools/resolve_indirect_symbols.py','tools/indirect_compute_probe.mm','tools/reproduce_indirect_compute.py','tools/verify_indirect_compute.py',
            'tools/make_metallib_transport_report.py','tools/package_metallib_transport.py','tools/run_signed_probe.py','src/indirect_compute_probe.metal','src/KeplerProgramImport.h']:
 files.add(ROOT/rel)
for rel in ['reports/STRATEGIE_KEPLERMETAL.txt','reports/STRATEGIE_PREUVES.json','reports/STRATEGIE_LIVRAISON.json','reports/MODERNISATION_NVIDIA_ACTUALISEE.json',
            'reports/MODERNISATION_NVIDIA_ACTUALISEE.csv','reports/METAL_CAPACITES_ACTUALISEES.json','reports/METAL_CAPACITES_ACTUALISEES.csv','reports/EXPERIMENTATIONS_PRIORISEES.json','tools/make_strategy_report.py']:
 files.add(LAB/'driver-research-2026-10-13'/rel)
selected=[];excluded=[];native={b'\xcf\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xce\xfa\xed\xfe',b'\xfe\xed\xfa\xce',b'\xca\xfe\xba\xbe',b'\x7fELF'}
for p in sorted(files):
 p.relative_to(LAB)
 with p.open('rb') as f:magic=f.read(4)
 if '__pycache__' in p.parts or p.suffix in ['.o','.a','.dylib'] or magic in native or p.name=='packet-delivery.json':excluded.append(str(p.relative_to(LAB)));continue
 if p.name.startswith('.env') or p.name in ['config.toml','id_rsa'] or 'coordinator.token' in p.name:raise SystemExit('Refusing credential/config candidate')
 selected.append(p)
entries=[{'path':str(p.relative_to(LAB)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in selected]
manifest={'files':entries,'excluded_host_binaries_and_caches':excluded,'executed_source_snapshots':True,'preparation_failures_and_negative_controls_preserved':True,
          'Qwen_job_ids':[],'system_modifications':False,'scope':'Incremental compiled-library/native transport evidence, not deployable driver or completed hardware support. Reproduction requires the existing pinned workspace and Apple toolchain.'}
with zipfile.ZipFile(out,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p,entry in zip(selected,entries):
  data=p.read_bytes();assert hashlib.sha256(data).hexdigest()==entry['sha256'];z.writestr(entry['path'],data)
 z.writestr('PACKET_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
with zipfile.ZipFile(out) as z:
 assert z.testzip() is None
 for entry in entries:
  data=z.read(entry['path']);assert len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256']
delivery={'path':str(out),'bytes':out.stat().st_size,'content_files':len(entries),'ZIP_entries':len(entries)+1,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'CRC_and_all_SHA256_verified':True,'Qwen_job_ids':[]}
(ROOT/'results/metallib-transport-progress/packet-delivery.json').write_text(json.dumps(delivery,indent=2)+'\n');print(json.dumps(delivery,indent=2))
