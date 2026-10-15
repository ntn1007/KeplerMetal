#!/usr/bin/env python3
"""Execute the exact prepared/verified host in a fresh signed process.

Explicit artifact reuse, not an automatic toolchain/SDK dependency cache.
Current source fingerprints and all referenced input artifacts must match.
"""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--from',dest='source',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--kind',choices=['dependency','cas','mixed'],required=True);a=p.parse_args()
old=a.source.resolve();old.relative_to(ROOT/'results');out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
inputs=json.loads((old/'inputs.json').read_text()); result=json.loads((old/'results.json').read_text()); verification=json.loads((old/'independent-verification.json').read_text());process=json.loads((old/'execution/manifest.json').read_text())
assert result['mode']=='prepare' and verification['status']=='PASS' and process['exit_code']==0 and not process['SIGKILL_requested'] and not process['authoritative_ps_status']
assert process['GPU_reservation']['state']=='terminal'
for name,h in inputs['source_hashes'].items():
 source=ROOT/('tools' if name.endswith('probe.mm') else 'src')/name
 assert sha(source)==h and sha(old/name)==h
exeName={'dependency':'cpu_icb_dependency_probe','cas':'cpu_icb_native_cas_probe','mixed':'cpu_icb_mixed_probe'}[a.kind]
assert sha(old/exeName)==process['original_binary_sha256']
out.mkdir();(out/'outputs').mkdir()
for name in inputs['source_hashes']:shutil.copyfile(old/name,out/name)
shutil.copyfile(old/exeName,out/exeName);(out/exeName).chmod(0o755)
if a.kind=='dependency':
 assert sha(old/'dependency.metallib')==inputs['library_SHA256'];shutil.copyfile(old/'dependency.metallib',out/'dependency.metallib')
 args=[str(out/'dependency.metallib'),str(out/'cpu_icb_dependency_manifest.json'),str(out/'outputs'),'execute']
elif a.kind=='cas':
 for name,h in inputs['assets_SHA256'].items():assert sha(old/'assets'/name)==h
 shutil.copytree(old/'assets',out/'assets')
 args=[str(out/'assets'),str(out/'cpu_icb_native_cas_manifest.json'),str(out/'outputs'),sha(out/'cpu_icb_native_cas_manifest.json'),'execute']
else:
 for name,key in [('cpu_icb_gpu_indices.metallib','compute_library_SHA256'),('render_state_carrier.metallib','render_library_SHA256')]:
  assert sha(old/name)==inputs[key];shutil.copyfile(old/name,out/name)
 args=[str(out/'cpu_icb_gpu_indices.metallib'),str(out/'cpu_icb_gpu_indices.json'),str(out/'render_state_carrier.metallib'),str(out/'outputs'),'execute']
inputs['explicit_host_reused_from']=str(old);inputs['reused_original_binary_SHA256']=sha(out/exeName);inputs['source_compilations']=0
(out/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
argv=['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(out/exeName),'--out',str(out/'execution'),'--timeout','30','--',*args]
r=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=45);(out/'observe.stdout').write_text(r.stdout);(out/'observe.stderr').write_text(r.stderr);(out/'commands.json').write_text(json.dumps([{'label':'fresh-process-from-pinned-host','argv':argv,'exit_code':r.returncode}],indent=2)+'\n');assert r.returncode==0,r.stderr[-2500:]
m=json.loads((out/'execution/manifest.json').read_text());assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'];d=json.loads((out/'execution/execution.stdout').read_text());(out/'results.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'mode':d['mode'],'PID':m['pid'],'source_compilations':0,'fresh_GPU_execution':True}))
