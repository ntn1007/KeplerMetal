#!/usr/bin/env python3
"""Observe native compiler containers in serialized, immutable signed processes."""
from pathlib import Path
import argparse, hashlib, json, struct, subprocess, sys, re
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
build=a.build.resolve();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
inputs=json.loads((build/'inputs.json').read_text());assert sha(build/'compiler_output_trace')==inputs['capture_executable_SHA256']
for n,h in inputs['source_hashes'].items():assert sha(build/n)==h
for n,h in inputs['assets_SHA256'].items():assert sha(build/'assets'/n)==h
driver=Path('/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver')
assert sha(driver)=='2b89839c425d95934f5e01f16c8683fe53432df410292ec8e554b21c98d6c054'
commands=[];records=[]
for name in ['local_control','local32','local256','local1024','pressure32','pressure64','pressure96']:
 case=out/name;case.mkdir();capture=case/'capture';capture.mkdir()
 cmd=[sys.executable,ROOT/'tools/run_signed_probe.py','--exe',build/'compiler_output_trace','--out',case/'execution','--timeout','15','--',build/'assets/local_memory.metallib',capture,'compute',name]
 cmd=list(map(str,cmd));r=subprocess.run(cmd,capture_output=True,text=True);(case/'launcher.stdout').write_text(r.stdout);(case/'launcher.stderr').write_text(r.stderr);commands.append({'label':name,'argv':cmd,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 if r.returncode:print(r.stdout,r.stderr);raise SystemExit(r.returncode)
 state=json.loads((case/'execution/manifest.json').read_text());assert state['exit_code']==0 and not state['SIGKILL_requested']and not state['authoritative_ps_status']
 observed=json.loads((case/'execution/execution.stdout').read_text());assert observed['pipeline_created']and not observed['gpu_dispatch']
 (case/'results.json').write_text(json.dumps(observed,indent=2)+'\n');payloads=[]
 for index,row in enumerate(observed['captures']):
  payload=Path(row['file']);b=payload.read_bytes();version,total=struct.unpack_from('<2I',b);assert version in[7,8,9]and total==len(b);offset=8;metadata=None;code=None
  for _ in range(32):
   next_,kind,size=struct.unpack_from('<QII',b,offset);assert offset+16+size<=len(b)
   if kind==0x10004:metadata=list(struct.unpack_from('<'+str(size//4)+'I',b,offset+16))
   if kind==0x10005:code=b[offset+16:offset+16+size]
   if not next_:break
   offset+=next_
  assert metadata is not None and len(metadata)==58 and code and len(code)%64==0
  file=capture/f'native-{index}.sass';file.write_bytes(code);decoder=ROOT/'build/envydis-only/envydis/envydis'
  cmd=[str(decoder),'-m','gf100','-V','gk104','-i','-n',str(file)];decoded=subprocess.run(cmd,capture_output=True,text=True,timeout=15);assert not decoded.returncode
  listing=capture/f'native-{index}.envydis.txt';listing.write_text(decoded.stdout)
  local_lines=[line for line in decoded.stdout.splitlines()if re.search(r'\bl\[|\b(?:ldl|stl)\b',line)]
  item={'compiler_output_SHA256':sha(payload),'metadata_words':metadata,'code_bytes':len(code),'code_SHA256':sha(file),'listing_SHA256':sha(listing),'local_memory_instruction_lines':local_lines,'unknown_annotations':decoded.stdout.count('[unknown'),'variant_SHA256':sha(Path(row['variant_file']))if row.get('variant_saved')else None}
  payloads.append(item)
 records.append({'function':name,'PID':state['pid'],'pipeline_created':True,'GPU_dispatch':False,'payloads':payloads});(out/'observations.json').write_text(json.dumps({'records':records,'driver_SHA256':sha(driver),'system_modified':False,'performance_benchmark':False},indent=2)+'\n')
 print(name,[(x['metadata_words'][7],len(x['local_memory_instruction_lines']),x['code_bytes'])for x in payloads],flush=True)
assert sha(driver)==inputs.get('driver_SHA256',sha(driver))
(out/'status.json').write_text(json.dumps({'status':'PASS','functions':len(records),'GPU_dispatch':False})+'\n')
