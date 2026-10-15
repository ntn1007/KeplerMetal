#!/usr/bin/env python3
"""Compare current production caller data with the current-source native M1."""
from pathlib import Path
import hashlib,json
from verify_command_ir_dataflow import verify
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results/command-ir-lifetime-progress-20261015';ref=ROOT/'results/command-ir-lifetime-M1-return-20261015/Reference';sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for e in json.loads((ref/'REFERENCE_RETURN.json').read_text())['files']:assert sha(ref/e['path'])==e['SHA256']
build=ROOT/'results/command-ir-lifetime-final-production-dataflow-build-20261015'
for name in ['command_ir_dataflow_client.mm','KeplerCPUICB.h']:assert sha(ref/name)==sha(build/name)
assert sha(ref/'gpu_command_frontend_dataflow.metal')==sha(ROOT/'src/gpu_command_frontend_dataflow.metal');rows=[];raw_equal=0
for mode in ['no_producer','barrier','no_consumer']:
 native=ref/'results'/mode;current=ROOT/'results'/('command-ir-lifetime-final-production-dataflow-20261015-'+mode);a,b=verify(native),verify(current);assert a['status']==b['status']=='PASS';files=[]
 for r,s in zip(json.loads((native/'results.json').read_text())['runs'],json.loads((current/'results.json').read_text())['runs']):
  assert r['specs']==s['specs']
  for name,f in r['files'].items():
   if name=='records':continue
   p=native/'outputs'/f;q=current/'outputs'/s['files'][name];assert p.read_bytes()==q.read_bytes();files.append({'file':f,'SHA256':sha(p)})
 raw_equal+=len(files);rows.append({'mode':mode,'native_trials':4,'files_identical':files})
assert raw_equal==156
result={'status':'PASS','native_trials':12,'raw_files_identical':raw_equal,'same_current_host_header_and_producer_sources':True,'rows':rows,'performance_benchmark':False}
with(OUT/'M1-comparison.json').open('x')as f:json.dump(result,f,indent=2);f.write('\n')
print(json.dumps({k:v for k,v in result.items()if k!='rows'}))
