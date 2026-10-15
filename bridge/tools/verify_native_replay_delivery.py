#!/usr/bin/env python3
"""Verify ZIP CRC/SHA and recalculate every replay cohort after extraction."""
from pathlib import Path,PurePosixPath
import argparse,hashlib,json,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--zip',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir()
cohorts=['native-replay-prepared','native-replay-gpu-l32-g1','native-replay-gpu-l33-g3','native-replay-gpu-l128-g5','native-replay-sequence-module-control','native-replay-mixed-prepared','native-replay-mixed-gpu'];tool_names=['decode_native_commands.py','verify_native_replay.py','verify_mixed_native_replay.py'];extract=out/'extracted';selected=[]
with zipfile.ZipFile(a.zip) as z:
 assert z.testzip() is None and len(z.namelist())==len(set(z.namelist()));manifest=json.loads(z.read('PACKET_MANIFEST.json'));entries=manifest['files'];assert len(z.namelist())==len(entries)+1
 for entry in entries:
  name=entry['path'];parts=PurePosixPath(name);assert not parts.is_absolute() and '..' not in parts.parts;data=z.read(name);assert len(data)==entry['bytes'] and hashlib.sha256(data).hexdigest()==entry['sha256']
  if any(name.startswith('bridge/results/'+cohort+'/') for cohort in cohorts) or name in ['bridge/tools/'+tool for tool in tool_names]:
   dest=extract/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data);selected.append(name)
checks=[]
for name in cohorts:
 script='verify_mixed_native_replay.py' if 'mixed' in name else 'verify_native_replay.py';directory=extract/'bridge/results'/name;argv=['python3',str(extract/'bridge/tools'/script),'--input',str(directory)];r=subprocess.run(argv,capture_output=True,text=True,timeout=30);(out/(name+'.stdout')).write_text(r.stdout);(out/(name+'.stderr')).write_text(r.stderr);assert r.returncode==0,r.stderr;result=json.loads((directory/'independent-verification.json').read_text());assert result['status']=='PASS';checks.append({'cohort':name,'exit_code':r.returncode,'result':result})
summary={'status':'PASS','archive':str(a.zip.resolve()),'archive_SHA256':hashlib.sha256(a.zip.read_bytes()).hexdigest(),'CRC_and_SHA256_content_files':len(entries),'extracted_files':len(selected),'portable_raw_verifier_cohorts':len(checks),'new_GPU_execution':False,'system_modifications':False,'results':checks};(out/'verification.json').write_text(json.dumps(summary,indent=2)+'\n');(out/Path(__file__).name).write_bytes(Path(__file__).read_bytes());print(json.dumps({k:v for k,v in summary.items() if k!='results'},indent=2))
