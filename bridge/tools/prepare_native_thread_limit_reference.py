#!/usr/bin/env python3
"""Freeze a source-only native Metal thread-limit reference; no SSH config."""
from pathlib import Path
import argparse,hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();build=a.build.resolve();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False);m=json.loads((build/'inputs.json').read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for n in ['native_thread_limit_probe.mm','limits.metal']:
 assert sha(build/n)==m['source_hashes'][n];shutil.copyfile(build/n,out/n)
(out/'run_reference.py').write_text('''from pathlib import Path
import hashlib,json,subprocess,platform
root=Path(__file__).resolve().parent
manifest=json.loads((root/'SOURCE_MANIFEST.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
assert platform.machine()=='arm64'
for n,h in manifest['files'].items():assert sha(root/n)==h
out=root/'output';out.mkdir(exist_ok=False);(out/'assets').mkdir();commands=[]
for name,cmd in [('metal',['xcrun','metal','-std=macos-metal2.1','-c',root/'limits.metal','-o',out/'limits.air']),('metallib',['xcrun','metallib',out/'limits.air','-o',out/'assets/limits.metallib']),('host',['xcrun','clang++','-arch','arm64','-O2','-std=c++17','-fobjc-arc',root/'native_thread_limit_probe.mm','-framework','Metal','-framework','Foundation','-o',out/'application']),('observe',[out/'application',out/'assets',out,'observe'])]:
 cmd=list(map(str,cmd));r=subprocess.run(cmd,capture_output=True,text=True,timeout=45);(out/(name+'.stdout')).write_text(r.stdout);(out/(name+'.stderr')).write_text(r.stderr);commands.append({'name':name,'argv':cmd,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\\n');assert not r.returncode,r.stderr[-1000:]
 if name=='observe':(out/'results.json').write_text(r.stdout)
for n,h in manifest['files'].items():assert sha(root/n)==h
(out/'FILE_MANIFEST.json').write_text(json.dumps({'files':{str(p.relative_to(root)):sha(p)for p in sorted(root.rglob('*'))if p.is_file()and p.name!='FILE_MANIFEST.json'},'user_GPU_command_buffers':0},indent=2)+'\\n')
print('PASS native M1 factory observation')
''')
(out/'SOURCE_MANIFEST.json').write_text(json.dumps({'files':{p.name:sha(p)for p in sorted(out.iterdir())},'user_GPU_command_buffers':0},indent=2)+'\n');print('PASS source reference',out)
