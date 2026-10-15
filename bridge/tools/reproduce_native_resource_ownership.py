#!/usr/bin/env python3
"""Build a signed, immutable read-only owner/allocator observation."""
from pathlib import Path
import argparse,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();commands=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(argv,label):
 r=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=45)
 (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':argv,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 print(label,r.returncode,flush=True);assert r.returncode==0,r.stderr[-3000:]
source=out/'native_resource_ownership.mm';source.write_bytes((ROOT/'tools'/source.name).read_bytes());exe=out/'native_resource_ownership'
library=ROOT/'results/indirect-compute-native-qualified/indirect_compute_probe.metallib';assert library.is_file()
run(['clang++','-O2','-std=c++17','-fobjc-arc',str(source),'-framework','Metal','-framework','Foundation','-o',str(exe)],'build')
run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(out/'execution'),'--timeout','20','--',str(library),str(out)],'observe')
execution=json.loads((out/'execution/manifest.json').read_text());assert execution['exit_code']==0 and not execution['SIGKILL_requested'] and not execution['authoritative_ps_status']
data=json.loads((out/'execution/execution.stdout').read_text());assert not data['committed'] and not data['GPU_dispatch'];assert all(row['status']==0 for row in data['records'])
if all('stream' in row for row in data['records']):
 captures=[]
 for row in data['records']:
  stream=row['stream'];assert row['range_comparable'] and stream['saved']
  captures.append({'mode':row['mode'],'step':row['step'],'file':stream['path'],'bytes':stream['bytes_read'],'SHA256':stream['SHA256']})
 (out/'capture.json').write_text(json.dumps({'records':captures,'args_GPU_address':data['objects']['args']['GPU_address'],'indirect_byte_offset':64,'GPU_dispatch':False,'committed':False},indent=2)+'\n')
(out/'ownership.json').write_text(json.dumps(data,indent=2)+'\n');(out/'inputs.json').write_text(json.dumps({'source_SHA256':sha(source),'library_path':str(library),'library_SHA256':sha(library),'Git_commit':None,'system_modifications':False,'Qwen_job_ids':[]},indent=2)+'\n')
(out/Path(__file__).name).write_bytes(Path(__file__).read_bytes());print(json.dumps({'records':len(data['records']),'GPU_dispatch':False,'status':'PASS'},indent=2))
