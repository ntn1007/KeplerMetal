#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1];LAB=ROOT.parent;out=ROOT/'KEPLERMETAL_REJEU_NATIF_2026-10-13.zip';assert not out.exists();files=set()
cohorts=['native-replay-prepared','native-replay-gpu-l32-g1','native-replay-gpu-l33-g3','native-replay-gpu-l128-g5','native-replay-sequence-module-control','native-replay-mixed-prepared','native-replay-mixed-gpu','native-replay-progress']
for name in cohorts:files.update(p for p in (ROOT/'results'/name).rglob('*') if p.is_file() and not p.is_symlink())
for rel in ['REJEU_NATIF_PERSISTANT.txt','results/hardware-coverage.json','src/KeplerNativeCommands.h','src/KeplerNativeCommands.mm','src/indirect_compute_probe.metal','tools/native_replay_probe.mm','tools/reproduce_native_replay.py','tools/verify_native_replay.py','tools/reproduce_mixed_native_replay.py','tools/verify_mixed_native_replay.py','tools/make_native_replay_report.py','tools/package_native_replay.py','tools/run_signed_probe.py','tools/decode_native_commands.py']:files.add(ROOT/rel)
for rel in ['reports/STRATEGIE_KEPLERMETAL.txt','reports/STRATEGIE_PREUVES.json','reports/STRATEGIE_LIVRAISON.json','reports/MODERNISATION_NVIDIA_ACTUALISEE.json','reports/MODERNISATION_NVIDIA_ACTUALISEE.csv','reports/METAL_CAPACITES_ACTUALISEES.json','reports/METAL_CAPACITES_ACTUALISEES.csv','reports/EXPERIMENTATIONS_PRIORISEES.json','tools/make_strategy_report.py']:files.add(LAB/'driver-research-2026-10-13'/rel)
envy=ROOT/'vendor/envytools-f102b82381f3f11cee113d16374c87091db039d9'
for rel in ['rnndb/graph/gk104_compute.xml','rnndb/graph/gk104_p2mf.xml','rnndb/fifo/nv_object.xml','rnndb/copyright.xml','demmt/pushbuf.c','COPYING']:
 p=envy/rel
 if p.exists():files.add(p)
selected=[];excluded=[];native={b'\xcf\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xce\xfa\xed\xfe',b'\xfe\xed\xfa\xce',b'\xca\xfe\xba\xbe',b'\x7fELF'}
for p in sorted(files):
 rel=str(p.relative_to(LAB));assert p.is_file() and not p.is_symlink()
 with p.open('rb') as f:magic=f.read(4)
 if '__pycache__' in p.parts or p.suffix in ['.o','.a','.dylib'] or magic in native or p.name=='packet-delivery.json':excluded.append(rel);continue
 if p.name.startswith('.env') or p.name in ['config.toml','id_rsa','id_ed25519'] or 'coordinator.token' in p.name:raise SystemExit('Credential/config candidate refused')
 selected.append(p)
entries=[{'path':str(p.relative_to(LAB)),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in selected]
manifest={'files':entries,'excluded_host_binaries_and_caches':excluded,'Qwen_job_ids':[],'system_modifications':False,'ICB_implemented':False,'integration_level':1,'all_hardware_functions_supported':False,'scope':'Incremental native packet replay sources/raw GPU evidence; not an installable driver. GPU rerun needs pinned iMac/workspace; portable Python raw verifiers included. Pipeline/profile and same queue restrictions explicit.'}
with zipfile.ZipFile(out,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for p,e in zip(selected,entries):
  data=p.read_bytes();assert hashlib.sha256(data).hexdigest()==e['sha256'];z.writestr(e['path'],data)
 z.writestr('PACKET_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
with zipfile.ZipFile(out) as z:
 assert z.testzip() is None and len(z.namelist())==len(entries)+1
 for e in entries:
  data=z.read(e['path']);assert len(data)==e['bytes'] and hashlib.sha256(data).hexdigest()==e['sha256']
delivery={'path':str(out),'bytes':out.stat().st_size,'content_files':len(entries),'ZIP_entries':len(entries)+1,'SHA256':hashlib.sha256(out.read_bytes()).hexdigest(),'CRC_and_all_SHA256_verified':True,'Qwen_job_ids':[]}
(ROOT/'results/native-replay-progress/packet-delivery.json').write_text(json.dumps(delivery,indent=2)+'\n');print(json.dumps(delivery,indent=2))
