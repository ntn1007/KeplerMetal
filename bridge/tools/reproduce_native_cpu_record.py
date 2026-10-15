#!/usr/bin/env python3
from pathlib import Path
import argparse,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();commands=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(argv,label):
 r=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':argv,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,r.returncode,flush=True);assert r.returncode==0,r.stderr[-3000:]
source=out/'native_cpu_record_probe.mm';source.write_bytes((ROOT/'tools'/source.name).read_bytes());exe=out/'native_cpu_record_probe';library=ROOT/'results/indirect-compute-native-qualified/indirect_compute_probe.metallib'
(out/'inputs.json').write_text(json.dumps({'source_SHA256':sha(source),'library_path':str(library),'library_SHA256':sha(library),'Git_commit':None,'Qwen_job_ids':[]},indent=2)+'\n');(out/Path(__file__).name).write_bytes(Path(__file__).read_bytes())
run(['clang++','-O2','-std=c++17','-fobjc-arc',str(source),'-framework','Metal','-framework','Foundation','-o',str(exe)],'build')
run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(out/'execution'),'--timeout','20','--',str(library),str(out)],'observe')
process=json.loads((out/'execution/manifest.json').read_text());assert process['exit_code']==0 and not process['SIGKILL_requested'] and not process['authoritative_ps_status'];r=json.loads((out/'execution/execution.stdout').read_text());assert not r['GPU_dispatch'] and not r['committed'];(out/'results.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({'rows':len(r['records']),'GPU_dispatch':False,'mapped_matches':[x['mapped_resource_entries_match'] for x in r['records']]},indent=2))
