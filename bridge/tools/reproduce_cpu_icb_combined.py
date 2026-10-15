#!/usr/bin/env python3
"""Freeze/build the shared scope plus optional native render transport."""
from pathlib import Path
import argparse, hashlib, json, subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();commands=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(argv,label):
 r=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':argv,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,r.returncode,flush=True);assert r.returncode==0,'\n'.join(x for x in r.stderr.splitlines() if 'error:' in x)[-3000:]
sources=[]
for folder,name in [('src','KeplerCPUICB.h'),('src','KeplerCPUICB.mm'),('src','KeplerNativeCommands.h'),('src','KeplerNativeCommands.mm'),('src','KeplerNativeRenderDraws.h'),('src','KeplerNativeRenderDraws.mm'),('tools','cpu_icb_combined_probe.mm'),('tools','verify_cpu_icb_combined.py'),('tools','decode_native_commands.py'),('src','cpu_icb_combined_profiles.json')]:
 f=out/name;f.write_bytes((ROOT/folder/name).read_bytes());sources.append(f)
(out/Path(__file__).name).write_bytes(Path(__file__).read_bytes());library=out/'render_state_carrier.metallib';library.write_bytes((ROOT/'results/render-state-final'/library.name).read_bytes())
vertex=out/'combined_render_resources.metallib';vertex.write_bytes((ROOT/'results/native-combined-arguments-passive'/vertex.name).read_bytes())
compute=out/'cpu_icb_gpu_indices.metallib';compute.write_bytes((ROOT/'results/native-gpu-indices-pipeline-captured'/compute.name).read_bytes());cm=out/'cpu_icb_gpu_indices.json';cm.write_bytes((ROOT/'src'/cm.name).read_bytes())
(out/'inputs.json').write_text(json.dumps({'source_hashes':{x.name:sha(x) for x in sources},'library_SHA256':sha(vertex),'legacy_library_SHA256':sha(library),'compute_library_SHA256':sha(compute),'compute_manifest_SHA256':sha(cm),'manifest_SHA256':sha(out/'cpu_icb_combined_profiles.json'),'Git_commit':None,'Qwen_job_ids':[],'system_modified':False},indent=2)+'\n')
exe=out/'cpu_icb_combined_probe';run(['clang++','-O2','-std=c++17','-fobjc-arc','-I',str(out),str(out/'cpu_icb_combined_probe.mm'),str(out/'KeplerCPUICB.mm'),str(out/'KeplerNativeCommands.mm'),str(out/'KeplerNativeRenderDraws.mm'),'-framework','Metal','-framework','Foundation','-o',str(exe)],'build')
raw=out/'outputs';raw.mkdir();run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(out/'execution'),'--timeout','30','--',str(compute),str(cm),str(library),str(vertex),str(out/'cpu_icb_combined_profiles.json'),str(raw),'execute' if a.execute else 'prepare'],'observe')
m=json.loads((out/'execution/manifest.json').read_text());assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'];d=json.loads((out/'execution/execution.stdout').read_text());(out/'results.json').write_text(json.dumps(d,indent=2)+'\n');assert d['passed'];print(json.dumps({'mode':d['mode'],'trials':len(d['runs']),'scope_restored':d['scope_restored'],'all_children_terminal':True},indent=2))
