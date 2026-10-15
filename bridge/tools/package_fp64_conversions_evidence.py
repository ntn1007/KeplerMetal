#!/usr/bin/env python3
"""Freeze this conversion/M1 milestone with per-file hashes, without new GPU runs."""
from pathlib import Path
import hashlib, json, zipfile

ROOT=Path(__file__).resolve().parents[1]
archive=ROOT/'KEPLERMETAL_CONVERSIONS_M1_2026-10-14.zip'
assert not archive.exists(), 'Preserve the existing evidence archive'
files=set()

def add(path):
    path=Path(path)
    if path.is_file():files.add(path)
    else:
        assert path.is_dir(), str(path)
        files.update(p for p in path.rglob('*') if p.is_file() and '__pycache__' not in p.parts)

sources=[
 'tools/fp64_math_compile.c','tools/build_fp64_math.py',
 'tools/fp64_conversion_inputs.py','tools/prepare_fp64_conversion_cases.py',
 'tools/verify_fp64_conversions.py','tools/run_fp64_math_case.py',
 'tools/verify_fp64_math.py','tools/build_combined_keplermetal_sdk.py',
 'tools/package_fp64_conversions_evidence.py',
 'tools/metal_reference_client.mm','tools/build_metal_reference.py',
 'tools/run_metal_reference.py','tools/verify_metal_reference.py',
 'tools/prepare_m1_reference_bundle.py','tools/lab_gpu_reservation.py',
 'src/KeplerFP64.h','src/KeplerFP64.mm',
 'src/cpu_icb_literal_lut.metal','src/cpu_icb_literal_lut_values.json',
 'sdk-combined/examples/fp64_client.mm','sdk-combined/examples/build_fp64_client.py',
 'sdk-combined/examples/run_fp64_client.py','sdk-combined/examples/verify_fp64_client.py',
 'sdk-combined/examples/fp64_conversion_client.mm',
 'sdk-combined/examples/build_fp64_conversion_client.py',
 'sdk-combined/examples/verify_fp64_conversion_client.py',
 'sdk-combined/runtime/run_sdk_host.py',
 'SDK_CONVERSIONS_FP64_2026-10-14.txt','REFERENCE_METAL_M1_GTX_2026-10-14.txt',
 'results/hardware-coverage.json',
]
for name in sources:add(ROOT/name)
results=[
 'fp64-conversions-offline-20261014','fp64-conversions-plans-20261014',
 'fp64-conversions-sdk-offline-20261014','fp64-conversions-small-suite-20261014',
 'combined-fp64-conversions-sdk-build-20261014',
 'combined-fp64-conversions-sdk-extracted-20261014',
 'combined-fp64-conversions-sdk-small-suite-20261014',
 'combined-fp64-conversions-sdk-qualification-suite-20261014',
 'combined-fp64-conversions-sdk-progress-20261014',
 'metal-reference-native-build-20261014-02',
 'metal-reference-adapter-build-20261014-02',
 'metal-reference-imac-summary-20261014',
 'm1-reference-source-bundle-20261014','m1-reference-transfer-20261014',
 'm1-gtx-reference-comparison-20261014',
]
for op in ['from_i64','from_u64','from_f32']:
 for mode in ['prepared','gpu']:results.append(f'fp64-conversions-{op}-l32-{mode}-20261014')
for label in ['small-prepared','small-gpu','prepared','gpu','no-producer','arithmetic-gpu','cas-gpu','literal-gpu']:
 results.append('combined-fp64-conversions-sdk-'+label+'-20261014')
for label in ['caps','native-icb','prepared','adapter','direct']:
 results.append('metal-reference-imac-'+label+'-20261014-02')
for name in results:add(ROOT/'results'/name)

sha=lambda path:hashlib.sha256(path.read_bytes()).hexdigest()
entries=[]
with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for path in sorted(files):
  name='bridge/'+str(path.relative_to(ROOT))
  raw=path.read_bytes();z.writestr(name,raw)
  entries.append({'path':name,'bytes':len(raw),'SHA256':hashlib.sha256(raw).hexdigest()})
 manifest={'files':entries,'Git_branch':'main','Git_commit':None,'goal_complete':False,'Qwen_job_ids':[],
           'scope':'L2 native SM30 conversions plus bounded M1 native ICB reference. No system driver installed or performance gain claimed.',
           'M1_returned_evidence':'bridge/results/m1-reference-transfer-20261014/KeplerMetalReference-M1-results-20261014.tar.gz',
           'M1_archive_manifest':'EVIDENCE_MANIFEST.json inside the nested M1 results tar'}
 z.writestr('FILE_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
with zipfile.ZipFile(archive) as z:
 assert len(z.namelist())==len(entries)+1
 for e in entries:
  raw=z.read(e['path']);assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['SHA256']
delivery={'archive':str(archive),'SHA256':sha(archive),'files':len(entries)+1,'bytes':archive.stat().st_size,'all_file_hashes_verified':True,'new_GPU_execution':False}
(ROOT/'results/combined-fp64-conversions-sdk-progress-20261014/evidence-delivery.json').write_text(json.dumps(delivery,indent=2)+'\n')
print(json.dumps(delivery,indent=2))
