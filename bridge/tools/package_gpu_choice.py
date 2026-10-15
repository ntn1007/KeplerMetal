#!/usr/bin/env python3
"""Package immutable source/raw evidence; refuse credentials and host binaries."""
from pathlib import Path
import argparse,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parents[1];LAB=ROOT.parent
p=argparse.ArgumentParser();p.add_argument('--name',default='KEPLERMETAL_CHOIX_GPU_RENDU_INDEXE_2026-10-14.zip');a=p.parse_args();archive=ROOT/a.name
assert Path(a.name).name==a.name and a.name.endswith('.zip') and not archive.exists()
cohorts=['gpu-argument-selector-passive', 'native-gpu-argument-choice-prepared', 'native-gpu-argument-choice-gpu-qualified', 'native-gpu-argument-choice-degenerate-prepared', 'native-gpu-argument-choice-degenerate-gpu-qualified', 'cpu-icb-gpu-choice-prepared', 'cpu-icb-gpu-choice-gpu-qualified', 'cpu-icb-gpu-choice-private-regression-prepared', 'cpu-icb-gpu-choice-private-regression-gpu-qualified', 'cpu-icb-gpu-choice-combined-regression-prepared', 'cpu-icb-gpu-choice-combined-regression-gpu-qualified', 'gpu-choice-progress', 'gpu-choice-source-baseline']
files=set()
for cohort in cohorts:files.update(x for x in (ROOT/'results'/cohort).rglob('*') if x.is_file() and not x.is_symlink())
for name in ['GPU_CHOIX_RENDU_INDEXE.txt', 'results/hardware-coverage.json', 'results/render-state-final/render_state_carrier.metallib', 'results/native-combined-arguments-passive/combined_render_resources.metallib', 'results/native-gpu-indices-pipeline-captured/cpu_icb_gpu_indices.metallib', 'results/native-private-arguments-gpu-qualified/private_fragment_resources.metallib', 'src/KeplerCPUICB.h', 'src/KeplerCPUICB.mm', 'src/KeplerNativeCommands.h', 'src/KeplerNativeCommands.mm', 'src/KeplerNativeRenderDraws.h', 'src/KeplerNativeRenderDraws.mm', 'src/gpu_argument_selector.metal', 'src/private_argument_selector.metal', 'src/combined_render_resources.metal', 'src/cpu_icb_combined_profiles.json', 'src/cpu_icb_private_argument_profiles.json', 'src/cpu_icb_gpu_indices.json', 'src/cpu_icb_gpu_indices.metal', 'tools/native_argument_selector_capture.mm', 'tools/reproduce_gpu_argument_selector.py', 'tools/native_gpu_argument_choice_probe.mm', 'tools/reproduce_native_gpu_argument_choice.py', 'tools/verify_native_gpu_argument_choice.py', 'tools/cpu_icb_gpu_choice_probe.mm', 'tools/reproduce_cpu_icb_gpu_choice.py', 'tools/verify_cpu_icb_gpu_choice.py', 'tools/cpu_icb_private_arguments_probe.mm', 'tools/reproduce_cpu_icb_private_arguments.py', 'tools/verify_cpu_icb_private_arguments.py', 'tools/cpu_icb_combined_probe.mm', 'tools/reproduce_cpu_icb_combined.py', 'tools/verify_cpu_icb_combined.py', 'tools/decode_native_commands.py', 'tools/run_signed_probe.py', 'tools/make_gpu_choice_report.py', 'tools/package_gpu_choice.py', 'tools/verify_gpu_choice_delivery.py']:files.add(ROOT/name)
research=LAB/'driver-research-2026-10-13'
for name in ['reports/STRATEGIE_KEPLERMETAL.txt','reports/STRATEGIE_PREUVES.json','reports/MODERNISATION_NVIDIA_ACTUALISEE.json','reports/MODERNISATION_NVIDIA_ACTUALISEE.csv','reports/METAL_CAPACITES_ACTUALISEES.json','reports/METAL_CAPACITES_ACTUALISEES.csv','reports/EXPERIMENTATIONS_PRIORISEES.json','tools/make_strategy_report.py']:files.add(research/name)
magic={b'\xcf\xfa\xed\xfe',b'\xfe\xed\xfa\xcf',b'\xce\xfa\xed\xfe',b'\xfe\xed\xfa\xce',b'\xca\xfe\xba\xbe',b'\x7fELF'};selected=[];excluded=[]
for f in sorted(files):
 assert f.is_file() and not f.is_symlink();rel=str(f.relative_to(LAB))
 if '__pycache__' in f.parts or f.suffix in ('.o','.a','.dylib') or f.read_bytes()[:4] in magic or f.name=='packet-delivery.json':excluded.append(rel);continue
 assert not f.name.startswith('.env') and f.name not in ('config.toml','id_rsa','id_ed25519','coordinator.token') and 'qwen-private' not in f.parts
 selected.append(f)
entries=[{'path':str(f.relative_to(LAB)),'bytes':f.stat().st_size,'sha256':hashlib.sha256(f.read_bytes()).hexdigest()} for f in selected]
manifest={'files':entries,'excluded_host_binaries_and_caches':excluded,'integration_level':1,'ICB_contract_complete':False,'GPU_resident_ICB_indirection':False,'all_hardware_functions_supported':False,'system_modified':False,'Qwen_job_ids':[],'scope':'Incremental native render source/raw evidence; bounded public CPU render ICB selectors qualified, not an installable driver. Portable verification does not re-attest omitted host executables or repeat GPU execution.'}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for f,e in zip(selected,entries):
  raw=f.read_bytes();assert hashlib.sha256(raw).hexdigest()==e['sha256'];z.writestr(e['path'],raw)
 z.writestr('PACKET_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
 assert z.testzip() is None
 for e in entries:
  raw=z.read(e['path']);assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['sha256']
delivery={'path':str(archive),'bytes':archive.stat().st_size,'content_files':len(entries),'SHA256':hashlib.sha256(archive.read_bytes()).hexdigest(),'CRC_and_all_SHA256_verified':True,'Qwen_job_ids':[]}
(ROOT/'results/gpu-choice-progress/packet-delivery.json').write_text(json.dumps(delivery,indent=2)+'\n');print(json.dumps(delivery,indent=2))
