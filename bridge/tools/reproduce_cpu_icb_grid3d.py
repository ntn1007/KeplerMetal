#!/usr/bin/env python3
"""Freeze sources, build, and run one bounded signed local profile probe."""
from pathlib import Path
import argparse, hashlib, json, subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args()
out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();commands=[]
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def run(argv,label):
 r=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=45)
 (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr)
 commands.append({'label':label,'argv':argv,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 print(label,r.returncode,flush=True);assert r.returncode==0,r.stderr[-4000:]
sources=[]
for sub,name in [('src','KeplerCPUICB.h'),('src','KeplerCPUICB.mm'),('src','KeplerNativeCommands.h'),('src','KeplerNativeCommands.mm'),('src','cpu_icb_grid3d.metal'),('src','cpu_icb_grid3d.json'),('tools','cpu_icb_grid3d_probe.mm')]:
 f=out/name;f.write_bytes((ROOT/sub/name).read_bytes());sources.append(f)
library=out/'cpu_icb_grid3d.metallib';library.write_bytes((ROOT/'results/native-grid3d-pipeline-captured'/library.name).read_bytes())
(out/Path(__file__).name).write_bytes(Path(__file__).read_bytes())
(out/'inputs.json').write_text(json.dumps({'source_hashes':{x.name:sha(x) for x in sources},'library_SHA256':sha(library),'manifest_SHA256':sha(out/'cpu_icb_grid3d.json'),'Git_commit':None,'Qwen_job_ids':[],'system_modified':False},indent=2)+'\n')
exe=out/'cpu_icb_grid3d_probe'
run(['clang++','-O2','-std=c++17','-fobjc-arc','-I',str(out),str(out/'cpu_icb_grid3d_probe.mm'),str(out/'KeplerCPUICB.mm'),str(out/'KeplerNativeCommands.mm'),'-framework','Metal','-framework','Foundation','-o',str(exe)],'build')
dest=out/'outputs';dest.mkdir();execution=out/'execution'
run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(execution),'--timeout','30','--',str(library),str(out/'cpu_icb_grid3d.json'),str(dest),'execute' if a.execute else 'prepare'],'observe')
m=json.loads((execution/'manifest.json').read_text());assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
d=json.loads((execution/'execution.stdout').read_text());(out/'results.json').write_text(json.dumps(d,indent=2)+'\n');assert d['passed']
print(json.dumps({'mode':d['mode'],'runs':len(d['runs']),'scope_restored':d['scope_restored'],'all_children_terminal':True},indent=2))
