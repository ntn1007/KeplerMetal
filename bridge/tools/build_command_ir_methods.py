#!/usr/bin/env python3
"""Compile additional public compute_command methods with an already built frontend."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
p=argparse.ArgumentParser();p.add_argument('--compiler-build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();base=a.compiler_build.resolve();out=a.out.resolve();out.relative_to(ROOT/'results')
manifest=json.loads((base/'manifest.json').read_text());assert manifest['status']=='PASS'
assert sha(base/'air_command_compile')==manifest['compiler_SHA256']
for path,h in manifest['fork_SHA256'].items():assert sha(base/path)==h
out.mkdir(exist_ok=False);shutil.copyfile(ROOT/'src/gpu_command_frontend_methods.metal',out/'methods.metal');commands=[];records=[]
def run(argv,label):
 r=subprocess.run([str(x)for x in argv],capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':[str(x)for x in argv],'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert r.returncode==0,r.stderr[-3000:];return r
run(['xcrun','metal','-std=macos-metal2.3','-c',out/'methods.metal','-o',out/'methods.air'],'metal')
for name in ['barrier','clear','threads','copy']:
 d=out/name;d.mkdir();(d/'backend-enabled').mkdir();shutil.copyfile(out/'methods.metal',d/'gpu_command_frontend.metal');shutil.copyfile(out/'methods.air',d/'producer.air')
 r=run([base/'air_command_compile',out/'methods.air',d/'backend-enabled','encode_public_'+name,'32','2','1'],name);info=json.loads(r.stdout);(d/'backend-enabled/info.json').write_text(json.dumps(info,indent=2)+'\n')
 assert info['command_ir_version']==1 and info['buffer_slots']==1 and info['push_bytes']==32 and info['scratch_bytes']==info['crs_bytes']==0 and 24<=info['registers']<=63
 records.append({'entry':'encode_public_'+name,'info':info})
 fork=d/'source-fork';shutil.copytree(base/'source-fork',fork)
 files=[Path(__file__).resolve(),ROOT/'src/gpu_command_frontend_methods.metal']
 derived={**manifest,'entry':'encode_public_'+name,'info':info,'parent_manifest_SHA256':sha(base/'manifest.json'),'input_SHA256':{str(x):sha(x)for x in files},'fork_SHA256':{str(x.relative_to(d)):sha(x)for x in fork.rglob('*')if x.is_file()}}
 (d/'manifest.json').write_text(json.dumps(derived,indent=2)+'\n')
(out/'receipt.json').write_text(json.dumps({'status':'PASS','records':records,'compiler_SHA256':sha(base/'air_command_compile'),'source_SHA256':sha(out/'methods.metal'),'GPU_execution':False},indent=2)+'\n');print(json.dumps(records,indent=2))
