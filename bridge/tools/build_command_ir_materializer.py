#!/usr/bin/env python3
"""Compile the fixed IR materializer offline and emit its exact hash."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--source',type=Path,default=ROOT/'src/command_ir_materializer.metal');a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);source=a.source.resolve();source.relative_to(ROOT/'src');shutil.copyfile(source,out/'command_ir_materializer.metal');commands=[]
for label,args in [('metal',['xcrun','metal','-std=macos-metal2.0','-c',str(out/'command_ir_materializer.metal'),'-o',str(out/'shader.air')]),('metallib',['xcrun','metallib',str(out/'shader.air'),'-o',str(out/'command_ir_materializer.metallib')])]:
 r=subprocess.run(args,capture_output=True,text=True,timeout=30);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':args,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert not r.returncode,r.stderr
sha=hashlib.sha256((out/'command_ir_materializer.metallib').read_bytes()).hexdigest();(out/'receipt.json').write_text(json.dumps({'status':'PASS','shader_SHA256':sha,'GPU_execution':False},indent=2)+'\n');print(sha)
