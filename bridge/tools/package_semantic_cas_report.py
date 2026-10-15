#!/usr/bin/env python3
"""Freeze the refinement, including raw controls and executed source snapshots.
No native host executables, system libraries, caches, credentials or Linux runs.
"""
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1];LAB=ROOT.parent;OUT=ROOT/'results/cas-icb-refinement'
archive=ROOT/'KEPLERMETAL_CAS_SEMANTIQUE_ICB_2026-10-13.zip';assert not archive.exists()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
files=set()
cohorts=['native-cas-repaired','native-cas-repaired-1024','native-cas-variants-captured','native-cas-semantic-qualification',
         'submission-benchmark-counted','submission-benchmark-three-modes','resource-sync-initial','resource-sync-alias',
         'icb-contract-inspection','icb-gpu-encoding-pipeline','cas-icb-refinement']
for name in cohorts:
 files.update(p for p in (ROOT/'results'/name).rglob('*') if p.is_file() and not p.is_symlink())
for rel in ['CAS_SEMANTIQUE_ICB.txt','results/native-cas-summary.json','results/resource-sync-summary.json','results/hardware-coverage.json',
            'tools/reproduce_semantic_cas_repair.py','tools/verify_semantic_cas_repair.py','tools/recognize_native_cas.py',
            'tools/prepare_native_cas_variants.py','tools/native_cas_air_dump.c','tools/air_cas_probe.mm','tools/run_signed_probe.py',
            'tools/reproduce_native_cas_repair.py','tools/extend_native_cas_repair.py','tools/verify_native_cas_repair.py',
            'tools/reproduce_submission_benchmark.py','tools/verify_submission_benchmark.py','tools/submission_benchmark.mm',
            'tools/icb_contract_probe.mm','tools/audit_icb_handlers.py','tools/reproduce_icb_gpu_compile.py','tools/compiler_output_trace.mm',
            'tools/make_semantic_cas_report.py','tools/package_semantic_cas_report.py',
            'src/KeplerProgramImport.h','src/KeplerProgramImport.mm','src/submission_benchmark.metal',
            'results/cas-lowering-final/threadgroup/test.metal','results/cas-lowering-final/threadgroup/test.air',
            'results/cas-lowering-final/threadgroup/test.metallib']:
 p=ROOT/rel;assert p.exists(),str(p);files.add(p)
research=LAB/'driver-research-2026-10-13'
for rel in ['tools/make_strategy_report.py','reports/MODERNISATION_NVIDIA_ACTUALISEE.json','reports/MODERNISATION_NVIDIA_ACTUALISEE.csv',
            'reports/METAL_CAPACITES_ACTUALISEES.json','reports/METAL_CAPACITES_ACTUALISEES.csv','reports/EXPERIMENTATIONS_PRIORISEES.json',
            'reports/STRATEGIE_KEPLERMETAL.txt','reports/STRATEGIE_PREUVES.json','reports/STRATEGIE_LIVRAISON.json',
            'reports/HISTORIQUE_KEPLER.json','inventory/components.json','inventory/inventory-manifest.json']:
 files.add(research/rel)
files.update(p for p in (research/'sources/icb-contract').rglob('*') if p.is_file())
selected=[];excluded=[];native={b'\xcf\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xce\xfa\xed\xfe',b'\xfe\xed\xfa\xce',b'\xca\xfe\xba\xbe',b'\x7fELF'}
for p in sorted(files):
 p.relative_to(LAB)
 with p.open('rb') as f:magic=f.read(4)
 if p.suffix in ['.o','.a','.dylib'] or magic in native or '__pycache__' in p.parts or p.name=='packet-delivery.json':
  excluded.append(str(p.relative_to(LAB)));continue
 if p.name.startswith('.env') or 'coordinator.token' in p.name or p.name in ['config.toml','id_rsa']:raise SystemExit('Refusing credential/config candidate')
 selected.append(p)
entries=[{'path':str(p.relative_to(LAB)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in selected]
manifest={'files':entries,'excluded_host_binaries_and_caches':excluded,'executed_source_snapshots_preserved':True,
          'raw_expected_failures_preserved':True,'Qwen_job_ids':[],'system_modifications':False,
          'scope':'Non-deployable source and evidence packet. Reproduction needs the existing pinned workspace/toolchain and compatible driver, not a Linux port or Metal3/4 installation.'}
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p,entry in zip(selected,entries):
  data=p.read_bytes();assert hashlib.sha256(data).hexdigest()==entry['sha256'];z.writestr(entry['path'],data)
 z.writestr('PACKET_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for entry in entries:
  data=z.read(entry['path']);assert len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256']
delivery={'path':str(archive),'bytes':archive.stat().st_size,'content_files':len(entries),'ZIP_entries':len(entries)+1,
          'sha256':sha(archive),'ZIP_CRC_and_every_SHA256_verified':True,'Qwen_job_ids':[]}
(OUT/'packet-delivery.json').write_text(json.dumps(delivery,indent=2)+'\n');print(json.dumps(delivery,indent=2))
