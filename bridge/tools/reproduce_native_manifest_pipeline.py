#!/usr/bin/env python3
from pathlib import Path
import argparse,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args()
out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();commands=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(argv,label):
 r=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':argv,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,r.returncode,flush=True);assert r.returncode==0,r.stderr[-3000:]
source=out/'cpu_icb_manifest.metal';source.write_bytes((ROOT/'src'/source.name).read_bytes())
host=out/'native_manifest_pipeline_probe.mm';host.write_bytes((ROOT/'tools'/host.name).read_bytes())
(out/Path(__file__).name).write_bytes(Path(__file__).read_bytes())
air=out/'cpu_icb_manifest.air';library=out/'cpu_icb_manifest.metallib';exe=out/'native_manifest_pipeline_probe'
run(['xcrun','metal','-std=macos-metal2.0','-c',str(source),'-o',str(air)],'compile-shader')
run(['xcrun','metallib',str(air),'-o',str(library)],'link-shader')
(out/'inputs.json').write_text(json.dumps({'source_hashes':{source.name:sha(source),host.name:sha(host)},'library_SHA256':sha(library),'Git_commit':None,'Qwen_job_ids':[]},indent=2)+'\n')
run(['clang++','-O2','-std=c++17','-fobjc-arc',str(host),'-framework','Metal','-framework','Foundation','-o',str(exe)],'build')
run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(out/'execution'),'--timeout','20','--',str(library),str(out)],'observe')
m=json.loads((out/'execution/manifest.json').read_text());assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
d=json.loads((out/'execution/execution.stdout').read_text());assert not d['committed'] and not d['GPU_dispatch'];(out/'results.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'library_SHA256':d['library_SHA256'],'records':d['records']},indent=2))
