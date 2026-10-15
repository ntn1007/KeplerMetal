#!/usr/bin/env python3
"""Build the current module against already diagnosed immutable assets."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--assets-from',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();sdk=out/'KeplerNativeCAS';sdk.mkdir();base=a.assets_from.resolve()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((base/'client-manifest.json').read_text());assert sha(base/m['library'])==m['library_SHA256']
for x in m['profiles']:assert sha(base/x['certificate'])==x['certificate_SHA256']
shutil.copytree(base,sdk/'assets')
for n in ['include','src','lib','examples']:(sdk/n).mkdir()
for n in ['KeplerNativeCAS.h','KeplerNativeCAS.mm','KeplerNativeCASAdapter.inc','KeplerProgramImport.h']:shutil.copyfile(ROOT/'src'/n,sdk/'src'/n)
shutil.copyfile(ROOT/'src/KeplerNativeCAS.h',sdk/'include/KeplerNativeCAS.h')
for n in ['client.mm','build_example.py']:shutil.copyfile(ROOT/'sdk-cas/examples'/n,sdk/'examples'/n)
commands=[]
def run(argv,label):
 r=subprocess.run(argv,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':argv,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,r.returncode,flush=True);assert r.returncode==0,r.stderr
obj=out/'KeplerNativeCAS.o';archive=sdk/'lib/libKeplerNativeCAS.a'
run(['clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-fvisibility=hidden','-I',str(sdk/'src'),'-c',str(sdk/'src/KeplerNativeCAS.mm'),'-o',str(obj)],'module')
run(['ar','rcs',str(archive),str(obj)],'static-library')
(sdk/'BUILD_MANIFEST.json').write_text(json.dumps({'Git_branch':'main','Git_commit':None,'source_SHA256':{str(x.relative_to(sdk)):sha(x) for x in (sdk/'src').iterdir()},'static_archive_SHA256':sha(archive),'object_SHA256':sha(obj),'assets_from':str(base),'assets_SHA256':{x.name:sha(x) for x in (sdk/'assets').iterdir()},'source_transport_provenance':json.loads((ROOT/'results/native-cas-sdk-source-provenance.json').read_text()),'commands':commands,'system_modified':False,'GPU_qualification_pending':True},indent=2)+'\n')
print('Module ready; GPU qualification pending',str(sdk))
