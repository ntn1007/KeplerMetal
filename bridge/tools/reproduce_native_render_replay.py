#!/usr/bin/env python3
"""Freeze/build one bounded native-render replay probe in an isolated cohort."""
from pathlib import Path
import argparse, hashlib, json, subprocess
ROOT = Path(__file__).resolve().parents[1]
p = argparse.ArgumentParser(); p.add_argument('--out', type=Path, required=True); p.add_argument('--execute', action='store_true'); a = p.parse_args()
out = a.out.resolve(); out.relative_to(ROOT / 'results'); assert not out.exists(); out.mkdir(); commands = []
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def run(argv, label):
    r = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True, timeout=45)
    (out / (label+'.stdout')).write_text(r.stdout); (out / (label+'.stderr')).write_text(r.stderr)
    commands.append({'label':label,'argv':argv,'exit_code':r.returncode}); (out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
    print(label,r.returncode,flush=True); assert r.returncode == 0,r.stderr[-4000:]
sources=[]
for folder,name in [('src','KeplerNativeRenderDraws.h'),('src','KeplerNativeRenderDraws.mm'),('tools','native_render_replay_probe.mm')]:
    f=out/name; f.write_bytes((ROOT/folder/name).read_bytes()); sources.append(f)
(out/Path(__file__).name).write_bytes(Path(__file__).read_bytes())
library=out/'render_state_carrier.metallib'; library.write_bytes((ROOT/'results/render-state-final'/library.name).read_bytes())
assert sha(library)=='965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7'
(out/'inputs.json').write_text(json.dumps({'source_hashes':{x.name:sha(x) for x in sources},'library_SHA256':sha(library),'Git_commit':None,'Qwen_job_ids':[],'system_modified':False},indent=2)+'\n')
exe=out/'native_render_replay_probe'
run(['clang++','-O2','-std=c++17','-fobjc-arc','-I',str(out),str(out/'native_render_replay_probe.mm'),str(out/'KeplerNativeRenderDraws.mm'),'-framework','Metal','-framework','Foundation','-o',str(exe)],'build')
raw=out/'outputs';raw.mkdir()
run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(out/'execution'),'--timeout','30','--',str(library),str(raw),'execute' if a.execute else 'prepare'],'observe')
m=json.loads((out/'execution/manifest.json').read_text());assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
d=json.loads((out/'execution/execution.stdout').read_text());(out/'results.json').write_text(json.dumps(d,indent=2)+'\n');assert d['passed']
print(json.dumps({'mode':d['mode'],'runs':len(d['runs']),'all_children_terminal':True,'render_ICB_implemented':False},indent=2))
