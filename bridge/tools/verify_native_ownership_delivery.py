#!/usr/bin/env python3
"""Verify every archive entry, then recalculate the GPU oracle from extracted data."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,json,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--zip',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();cohort='bridge/results/indirect-descriptor-gpu-readback/';selected=[]
with zipfile.ZipFile(a.zip) as z:
 names=z.namelist();assert len(names)==len(set(names)) and z.testzip() is None;manifest=json.loads(z.read('PACKET_MANIFEST.json'));entries=manifest['files'];assert len(names)==len(entries)+1
 for entry in entries:
  name=entry['path'];path=PurePosixPath(name);assert not path.is_absolute() and '..' not in path.parts
  data=z.read(name);assert len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256']
  if name.startswith(cohort) or name in ['bridge/tools/verify_indirect_descriptor_readback.py','bridge/tools/decode_native_commands.py']:
   dest=out/'extracted'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);selected.append(name)
exe=out/'extracted/bridge/tools/verify_indirect_descriptor_readback.py';data=out/'extracted'/cohort
argv=['python3',str(exe),'--input',str(data)];r=subprocess.run(argv,capture_output=True,text=True,timeout=30);(out/'verification.stdout').write_text(r.stdout);(out/'verification.stderr').write_text(r.stderr);assert r.returncode==0,r.stderr
result=json.loads((data/'independent-verification.json').read_text());assert result['status']=='PASS' and result['QMD_words_changed']==24 and result['constant_state_words_changed']==108 and result['consumer_invocations']==4917
summary={'status':'PASS','archive':str(a.zip.resolve()),'archive_SHA256':hashlib.sha256(a.zip.read_bytes()).hexdigest(),'CRC_and_SHA256_content_files':len(entries),'extracted_files':len(selected),'portable_raw_verifier_exit_code':r.returncode,'raw_GPU_observations_reread':{k:v for k,v in result.items() if k!='records'},'command':argv,'new_GPU_execution':False,'system_modifications':False}
(out/'verification.json').write_text(json.dumps(summary,indent=2)+'\n');(out/Path(__file__).name).write_bytes(Path(__file__).read_bytes());print(json.dumps({k:v for k,v in summary.items() if k not in ['raw_GPU_observations_reread','command']},indent=2))
