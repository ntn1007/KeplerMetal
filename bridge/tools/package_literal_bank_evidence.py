#!/usr/bin/env python3
"""Freeze CB0/reservation evidence; check all members and eleven raw oracles."""
from pathlib import Path
import hashlib,json,sys,zipfile
ROOT=Path(__file__).resolve().parents[1];LAB=ROOT.parent
archive=ROOT/'KEPLERMETAL_CB0_LUT_RESERVATION_2026-10-14.zip'
check=ROOT/'results/literal-bank-portable-verification-20261014';assert not archive.exists() and not check.exists()
files=set()
for pattern in ['literal-lut-*','literal-bank-*','native-literal-bank-*','gpu-reservation-cpu-tests-20261014*']:
 for folder in (ROOT/'results').glob(pattern):files.update(p for p in folder.rglob('*') if p.is_file())
names=['CB0_TABLES_NATIVES_RESERVATION.txt','results/hardware-coverage.json','tools/lab_gpu_reservation.py','tools/lab_phase_timing.py','tools/test_lab_gpu_reservation.py','tools/run_signed_probe.py','tools/reuse_prepared_lab_host.py','tools/make_literal_bank_report.py','tools/package_literal_bank_evidence.py','tools/reproduce_cpu_icb_literal_lut.py','tools/verify_cpu_icb_literal_lut.py','tools/cpu_icb_literal_lut_probe.mm','tools/native_literal_bank_passive_probe.mm','tools/verify_cpu_icb_dependency.py','tools/verify_cpu_icb_native_cas.py','tools/verify_cpu_icb_mixed.py','tools/decode_native_commands.py','src/cpu_icb_literal_lut.metal','src/cpu_icb_literal_lut_manifest.json','src/cpu_icb_literal_lut_values.json']
for stem in ['KeplerCPUICB','KeplerNativeCommands','KeplerNativeRenderDraws','KeplerNativeCAS','KeplerProgramImport']:
 names.extend('src/'+stem+suffix for suffix in ['.h','.mm'])
names.append('src/KeplerNativeCASAdapter.inc')
files.update(ROOT/n for n in names)
groups={'lut':['literal-lut-prepared-20261014-02','literal-lut-reject-unqualified-20261014','literal-lut-reject-size-20261014','literal-lut-gpu-qualified-20261014','literal-lut-native-reference-20261014'],
 'dependency':['literal-bank-dependency-regression-prepared-20261014','literal-bank-dependency-regression-gpu-20261014'],
 'cas':['literal-bank-cas-regression-prepared-20261014','literal-bank-cas-regression-gpu-20261014'],
 'mixed':['literal-bank-mixed-regression-prepared-20261014','literal-bank-mixed-regression-gpu-20261014']}
for group in groups.values():
 for name in group:
  for n in json.loads((ROOT/'results'/name/'inputs.json').read_text())['source_hashes']:
   files.add(ROOT/('tools' if n.endswith('probe.mm') else 'src')/n)
magic={b'\xcf\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xce\xfa\xed\xfe',b'\xfe\xed\xfa\xce',b'\xca\xfe\xba\xbe',b'\xbe\xba\xfe\xca',b'\x7fELF'}
selected=[];excluded=[]
for p in sorted(files):
 assert p.is_file() and not p.is_symlink(),str(p)
 assert p.name not in ['coordinator.token','config.toml','id_rsa','id_ed25519'] and not p.name.startswith('.env') and 'qwen-private' not in p.parts
 raw=p.read_bytes();rel=str(p.relative_to(LAB))
 if '__pycache__' in p.parts or p.suffix in ['.o','.a','.dylib'] or raw[:4] in magic or p.name=='packet-delivery.json':excluded.append(rel);continue
 selected.append((rel,raw))
entries=[{'path':n,'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest()} for n,raw in selected]
manifest={'files':entries,'excluded_host_binaries_and_caches':excluded,'integration_level':1,'full_ICB_contract':False,'all_hardware_supported':False,'system_modified':False,'Qwen_job_ids':[],'scope':'CB0 LUT qualification, lifecycle reservation CPU tests and raw regressions. Portable verification omits executable re-attestation and does not run GPU tests. Isolated reservation-fixture unresolved states are tests, not the live lab state.'}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED) as z:
 for n,raw in selected:z.writestr(n,raw)
 z.writestr('PACKET_MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for e in entries:
  raw=z.read(e['path']);assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['sha256']
 check.mkdir();z.extractall(check)
sys.path.insert(0,str(check/'bridge/tools'))
from verify_cpu_icb_literal_lut import verify as lut
from verify_cpu_icb_dependency import verify as dependency
from verify_cpu_icb_native_cas import verify as cas
from verify_cpu_icb_mixed import verify as mixed
results={}
for kind,group in groups.items():
 for name in group:
  v={'lut':lut,'dependency':dependency,'cas':cas,'mixed':mixed}[kind](check/'bridge/results'/name,current=True,portable=True);assert v['status']=='PASS';results[name]={k:value for k,value in v.items() if k!='raw_SHA256'}
(check/'verification.json').write_text(json.dumps(results,indent=2)+'\n')
delivery={'path':str(archive),'files':len(entries),'bytes':archive.stat().st_size,'SHA256':hashlib.sha256(archive.read_bytes()).hexdigest(),'all_CRC_SHA_verified':True,'portable_oracles':len(results),'fresh_GPU_execution':False,'Qwen_job_ids':[]}
(ROOT/'results/literal-bank-progress/packet-delivery.json').write_text(json.dumps(delivery,indent=2)+'\n');print(json.dumps(delivery,indent=2))
