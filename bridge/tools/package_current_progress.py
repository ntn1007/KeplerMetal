#!/usr/bin/env python3
"""Source/raw-evidence packet; no native executables, private tokens or caches."""
from pathlib import Path
import hashlib,json,stat,zipfile
ROOT=Path(__file__).resolve().parents[1];LAB=ROOT.parent
out=ROOT/'KEPLERMETAL_CAS_RESSOURCES_CPU_2026-10-13.zip';assert not out.exists()
files=set()
for name in ['native-cas-repaired','native-cas-repaired-1024','air-cas-extended','resource-sync-initial','resource-sync-alias','submission-benchmark-counted','current-progress']:
 files.update(p for p in (ROOT/'results'/name).rglob('*') if p.is_file() and not p.is_symlink())
for rel in ['PROGRES_CAS_RESSOURCES_CPU.txt','results/native-cas-summary.json','results/resource-sync-summary.json','results/hardware-coverage.json',
 'tools/reproduce_native_cas_repair.py','tools/extend_native_cas_repair.py','tools/verify_native_cas_repair.py',
 'tools/reproduce_air_cas_extended.py','tools/verify_air_cas_extended.py','tools/air_cas_probe.mm','tools/air_cas_compile.c',
 'tools/prepare_cas_lowering.py','tools/reproduce_air_cas.py','tools/verify_air_cas.py',
 'tools/resource_sync_probe.mm','tools/reproduce_resource_sync.py','tools/verify_resource_sync.py',
 'tools/submission_benchmark.mm','tools/reproduce_submission_benchmark.py','tools/verify_submission_benchmark.py',
 'tools/make_current_progress_report.py','tools/package_current_progress.py','tools/run_signed_probe.py',
 'src/resource_sync_probe.metal','src/submission_benchmark.metal','src/air_cas_carrier.metal',
 'src/KeplerProgramImport.h','src/KeplerProgramImport.mm','src/opennvda-air-cas-result.patch',
 'results/cas-lowering-final/threadgroup/test.metal','results/cas-lowering-final/threadgroup/test.air','results/cas-lowering-final/threadgroup/test.metallib']:
 p=ROOT/rel
 if p.is_file():files.add(p)
for rel in ['tools/make_strategy_report.py','reports/STRATEGIE_KEPLERMETAL.txt','reports/METAL_CAPACITES_ACTUALISEES.json',
            'reports/MODERNISATION_NVIDIA_ACTUALISEE.json','reports/EXPERIMENTATIONS_PRIORISEES.json','reports/STRATEGIE_PREUVES.json','reports/STRATEGIE_LIVRAISON.json']:
 files.add(LAB/'driver-research-2026-10-13'/rel)
filtered=[];excluded=[]
native_magic={b'\xcf\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xce\xfa\xed\xfe',b'\xfe\xed\xfa\xce',b'\xca\xfe\xba\xbe',b'\x7fELF'}
for p in sorted(files):
 p.relative_to(LAB)
 with p.open('rb') as f:magic=f.read(4)
 if p.suffix in ['.o','.a','.dylib'] or magic in native_magic or '__pycache__' in p.parts:
  excluded.append(str(p.relative_to(LAB)));continue
 if p.name.startswith('.env') or 'coordinator.token' in p.name:raise SystemExit('Refusing secret candidate')
 filtered.append(p)
entries=[{'path':str(p.relative_to(LAB)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in filtered]
manifest={'files':entries,'excluded_native_binaries':excluded,'includes_executed_source_snapshots':True,'includes_negative_controls':True,
 'requirements':'Reproduction scripts require the existing workspace/pinned upstream dependencies and Apple toolchain. This packet is not a deployable driver.',
 'system_changes':False,'Qwen_jobs':[]}
with zipfile.ZipFile(out,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p,entry in zip(filtered,entries):
  data=p.read_bytes();assert hashlib.sha256(data).hexdigest()==entry['sha256'];z.writestr(entry['path'],data)
 z.writestr('PACKET_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
with zipfile.ZipFile(out) as z:
 assert z.testzip() is None
 for entry in entries:assert hashlib.sha256(z.read(entry['path'])).hexdigest()==entry['sha256']
delivery={'path':str(out),'bytes':out.stat().st_size,'files':len(entries)+1,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'ZIP_CRC_and_all_SHA256_verified':True}
(ROOT/'results/current-progress/packet-delivery.json').write_text(json.dumps(delivery,indent=2)+'\n')
print(json.dumps(delivery,indent=2))
