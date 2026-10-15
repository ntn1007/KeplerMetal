#!/usr/bin/env python3
from pathlib import Path
import argparse,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();commands=[]
def run(argv,label):
 r=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':argv,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,r.returncode,flush=True);assert r.returncode==0,r.stderr[-3000:]
source=out/'native_retention_probe.mm';source.write_bytes((ROOT/'tools'/source.name).read_bytes());exe=out/'native_retention_probe';library=ROOT/'results/indirect-compute-native-qualified/indirect_compute_probe.metallib'
run(['clang++','-O2','-std=c++17','-fobjc-arc',str(source),'-framework','Metal','-framework','Foundation','-o',str(exe)],'build')
run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(out/'execution'),'--timeout','20','--',str(library)],'observe')
execution=json.loads((out/'execution/manifest.json').read_text());assert execution['exit_code']==0 and not execution['SIGKILL_requested'] and not execution['authoritative_ps_status']
result=json.loads((out/'execution/execution.stdout').read_text());assert not result['committed'] and not result['GPU_dispatch'];(out/'retention.json').write_text(json.dumps(result,indent=2)+'\n')
(out/'inputs.json').write_text(json.dumps({'source_SHA256':hashlib.sha256(source.read_bytes()).hexdigest(),'library_path':str(library),'library_SHA256':hashlib.sha256(library.read_bytes()).hexdigest(),'Git_commit':None,'Qwen_job_ids':[]},indent=2)+'\n');(out/Path(__file__).name).write_bytes(Path(__file__).read_bytes());print('Completed own-process lifetime observations')
