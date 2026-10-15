#!/usr/bin/env python3
"""Freeze this milestone; verify its bytes and portable oracles, without GPU runs."""
from pathlib import Path
import hashlib, json, sys, zipfile

ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
archive=ROOT/'KEPLERMETAL_ICB_ASYNCHRONE_2026-10-14.zip'
assert not archive.exists()
selected=set()
def add(p):
    p=Path(p);p.relative_to(ROOT)
    if p.is_file():selected.add(p)
    elif p.is_dir():
        for f in p.rglob('*'):
            if f.is_file() and f.suffix not in ['.o','.pyc'] and '__pycache__' not in f.parts:selected.add(f)
    else:raise FileNotFoundError(p)

for p in (ROOT/'results').glob('resident-async-*'):add(p)
for pattern in ['resident-mixed-imac-*-20261014','resident-mixed-regression-graph-*-20261014','resident-mixed-regression-baseline-*-20261014','resident-mixed-refusal-*-20261014']:
    for p in (ROOT/'results').glob(pattern):
        if (p/'outputs').is_dir():add(p/'outputs')
add(ROOT/'ICB_ASYNCHRONE_M1_GTX_2026-10-14.txt')
for n in ['KeplerCPUICB.h','KeplerCPUICB.mm','KeplerNativeCommands.h','KeplerNativeCommands.mm','cpu_icb_profiles.metal']:add(ROOT/'src'/n)
for n in ['build_combined_keplermetal_sdk.py','run_resident_qmd_copy.py','verify_cpu_icb_gpu_copy.py','verify_cpu_icb_copy_graph.py','verify_cpu_icb_copy_mixed.py','verify_cpu_icb_copy_refusals.py','verify_cpu_icb_copy_async.py','run_m1_copy_async_reference.py','native_enqueue_status.mm','shared_event_watchdog_probe.mm','collect_m1_gpu_copy_reference.py','package_resident_async_evidence.py','lab_gpu_reservation.py']:add(ROOT/'tools'/n)
for n in ['cpu_icb_copy_graph_client.mm','build_cpu_icb_copy_graph_client.py','cpu_icb_gpu_copy_client.mm','build_cpu_icb_gpu_copy_client.py','cpu_icb_copy_mixed_client.mm','build_cpu_icb_copy_mixed_client.py','cpu_icb_copy_refusal_client.mm','build_cpu_icb_copy_refusal_client.py','cpu_icb_copy_async_client.mm','build_cpu_icb_copy_async_client.py']:add(ROOT/'sdk-combined/examples'/n)
add(ROOT/'sdk-combined/runtime/run_sdk_host.py')
entries=[{'path':'bridge/'+str(p.relative_to(ROOT)),'bytes':p.stat().st_size,'SHA256':sha(p)}for p in sorted(selected)]
manifest={'files':entries,'date':'2026-10-14','Git':{'branch':'main','commit':None},'Qwen_job_ids':[],
          'objective_complete':False,'system_modified':False,'performance_benchmark':False,
          'scope':'Native M1 behavior reference and bounded L2 GTX same-queue asynchronous mixed-pipeline copies without intermediate CPU completion waits'}
with zipfile.ZipFile(archive,'x',zipfile.ZIP_DEFLATED,compresslevel=6,strict_timestamps=False)as z:
    for p in sorted(selected):z.write(p,'bridge/'+str(p.relative_to(ROOT)))
    z.writestr('PACKET_MANIFEST.json',json.dumps(manifest,indent=2)+'\n')
check=ROOT/'results/resident-async-packet-check-20261014';check.mkdir(exist_ok=False)
with zipfile.ZipFile(archive)as z:
    assert len(z.namelist())==len(entries)+1 and len(set(z.namelist()))==len(z.namelist())
    for e in entries:
        raw=z.read(e['path']);assert len(raw)==e['bytes'] and hashlib.sha256(raw).hexdigest()==e['SHA256']
    for n in z.namelist():assert not n.startswith('/') and '..' not in Path(n).parts
    z.extractall(check)
frozen=check/'bridge';sdk=frozen/'results/resident-async-sdk-build-20261014/KeplerMetalSDK'
sdk_manifest=json.loads((sdk/'FILE_MANIFEST.json').read_text())
for e in sdk_manifest['files']:assert sha(sdk/e['path'])==e['SHA256'] and (sdk/e['path']).stat().st_size==e['bytes']
sys.path.insert(0,str(sdk/'examples'))
from verify_cpu_icb_copy_graph import verify as graph
from verify_cpu_icb_copy_mixed import verify as mixed
from verify_cpu_icb_copy_async import verify as asynchronous
from verify_cpu_icb_copy_refusals import verify as refusals
from verify_cpu_icb_gpu_copy import verify as baseline
from verify_fp64_reverse_client import verify as reverse
from verify_fp64_client import verify as arithmetic
from verify_example import verify as cas
from verify_literal_client import verify as literal
checks=[]
def test(p,fn):
    v=fn(p,portable=True);checks.append({'path':str(p.relative_to(check)),'status':v['status']})
for p in sorted((frozen/'results').glob('resident-async-imac-*-20261014')):test(p,asynchronous)
for p in sorted((frozen/'results/resident-async-M1-return-20261014/GPUCopyReturn/results').glob('*')):
    if (p/'results.json').exists():test(p,asynchronous)
for p in sorted((frozen/'results').glob('resident-async-regression-refusal-*-20261014')):test(p,refusals)
for variant,fn in [('mixed',mixed),('graph',graph),('baseline',baseline)]:
    for p in sorted((frozen/'results').glob('resident-async-regression-'+variant+'-*-20261014')):test(p,fn)
for n,fn in [('reverse',reverse),('arithmetic',arithmetic),('cas',cas),('literal',literal)]:test(frozen/'results'/('resident-async-regression-'+n+'-20261014'),fn)
assert len(checks)==95
raw_comparisons=0
for variant,prefix in [('mixed','resident-mixed-imac-'),('graph','resident-mixed-regression-graph-'),('baseline','resident-mixed-regression-baseline-')]:
    for p in sorted((frozen/'results').glob('resident-async-regression-'+variant+'-*-20261014')):
        case=p.name[len('resident-async-regression-'+variant+'-'):-len('-20261014')];old=frozen/'results'/(prefix+case+'-20261014')
        for f in sorted((p/'outputs').glob('*.bin')):assert f.read_bytes()==(old/'outputs'/f.name).read_bytes();raw_comparisons+=1
for p in sorted((frozen/'results').glob('resident-async-regression-refusal-*-20261014')):
    mode=p.name[len('resident-async-regression-refusal-'):-len('-20261014')];old=frozen/'results'/('resident-mixed-refusal-'+mode+'-20261014')
    for f in sorted((p/'outputs').glob('*.bin')):assert f.read_bytes()==(old/'outputs'/f.name).read_bytes();raw_comparisons+=1
assert raw_comparisons==1332
p=frozen/'results/resident-async-enqueue-probe-20261014';d=json.loads((p/'results.json').read_text());recovery=json.loads((p/'execution/recovery.json').read_text());job=recovery['registry_job'];assert [d['initial_status'],d['enqueued_status'],d['final_status']]==[0,1,4] and d['user_kernel_dispatches']==0 and job['exit_code']==0 and not job['SIGKILL_requested'];assert sha(p/'application')==job['original_binary_sha256'] and sha(p/'execution/application')==job['signed_binary_sha256'];assert recovery['reservation_snapshot']['state']=='terminal' and recovery['reservation_snapshot']['child_PID']==job['pid'];checks.append({'path':str(p.relative_to(check)),'status':'PASS_RECOVERED_ENQUEUE'})
p=frozen/'results/resident-async-watchdog-probe-20261014';d=json.loads((p/'results.json').read_text());m=json.loads((p/'execution/manifest.json').read_text());assert d['status']=='PASS_EXPECTED_WATCHDOG_RELEASE' and d['watchdog_fired'] and d['marker_before_guard']==0 and d['marker_final']==d['marker_expected'] and d['final_status']==4 and m['exit_code']==0 and not m['SIGKILL_requested'];assert sha(p/'application')==m['original_binary_sha256'] and sha(p/'execution/application')==m['signed_binary_sha256'];checks.append({'path':str(p.relative_to(check)),'status':'PASS_WATCHDOG_RELEASE'})
assert len(checks)==97
result={'status':'PASS','archive_SHA256':sha(archive),'manifest_files_verified':len(entries),
        'SDK_manifest_files_verified':len(sdk_manifest['files']),
        'portable_oracles':checks,'portable_oracle_count':len(checks),
        'nonregression_raw_files_compared':raw_comparisons,'new_GPU_runs':0,'extracted_binaries_executed':False}
(check/'portable-verification.json').write_text(json.dumps(result,indent=2)+'\n')
delivery={'path':str(archive),'SHA256':sha(archive),'bytes':archive.stat().st_size,'files':len(entries)+1,
          'status':'PASS','portable_oracles':len(checks),'system_modified':False,'objective_complete':False}
(ROOT/'results/resident-async-progress-20261014/packet-delivery.json').write_text(json.dumps(delivery,indent=2)+'\n')
print(json.dumps(delivery,indent=2))
