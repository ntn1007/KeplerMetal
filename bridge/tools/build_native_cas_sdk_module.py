#!/usr/bin/env python3
"""Build the current module against already diagnosed immutable assets."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
from public_large_scratch import check_driver_profile
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--assets-from',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--require-decoder-evidence',action='store_true');a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();base=a.assets_from.resolve()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
m=json.loads((base/'client-manifest.json').read_text());assert sha(base/m['library'])==m['library_SHA256']
for x in m['profiles']:assert sha(base/x['certificate'])==x['certificate_SHA256']
if a.require_decoder_evidence:
 driver=check_driver_profile()
 if m.get('driver_SHA256')!=driver:raise SystemExit('SDK asset driver profile differs')
 for x in m['profiles']:
  cert=json.loads((base/x['certificate']).read_text())
  if type(x.get('candidate')) is not bool or cert.get('candidate') is not x['candidate']:raise SystemExit('Certificate candidate value differs')
  if x['candidate'] and cert.get('decoder_reproduced_listing') is not True:raise SystemExit('Candidate lacks decoder reproduction evidence')
out.mkdir();sdk=out/'KeplerNativeCAS';sdk.mkdir()
shutil.copytree(base,sdk/'assets')
for n in ['include','src','lib','examples']:(sdk/n).mkdir()
for n in ['KeplerNativeCAS.h','KeplerNativeCAS.mm','KeplerConditionalAux.h','KeplerNativeCASAdapter.inc','KeplerProgramImport.h','KeplerGPUIdentity.h','KeplerDriverProfile.h','KeplerNativeAllocation.h','KeplerNativeAllocation.inc']:shutil.copyfile(ROOT/'src'/n,sdk/'src'/n)
shutil.copyfile(ROOT/'src/KeplerNativeCAS.h',sdk/'include/KeplerNativeCAS.h')
shutil.copyfile(ROOT/'src/KeplerGPUIdentity.h',sdk/'include/KeplerGPUIdentity.h')
for n in ['client.mm','build_example.py']:shutil.copyfile(ROOT/'sdk-cas/examples'/n,sdk/'examples'/n)
commands=[]
def run(argv,label):
 r=subprocess.run(argv,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':argv,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,r.returncode,flush=True);assert r.returncode==0,r.stderr
obj=out/'KeplerNativeCAS.o';archive=sdk/'lib/libKeplerNativeCAS.a'
run(['clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-fvisibility=hidden','-I',str(sdk/'src'),'-c',str(sdk/'src/KeplerNativeCAS.mm'),'-o',str(obj)],'module')
run(['ar','rcs',str(archive),str(obj)],'static-library')
if a.require_decoder_evidence and check_driver_profile()!=driver:raise SystemExit('Driver profile changed during SDK build')
(sdk/'BUILD_MANIFEST.json').write_text(json.dumps({'Git_branch':None,'Git_commit':None,'source_SHA256':{str(x.relative_to(sdk)):sha(x) for x in (sdk/'src').iterdir()},'example_SHA256':{str(x.relative_to(sdk)):sha(x) for x in (sdk/'examples').iterdir()},'static_archive_SHA256':sha(archive),'object_SHA256':sha(obj),'assets_from':str(base),'assets_SHA256':{x.name:sha(x) for x in (sdk/'assets').iterdir()},'decoder_evidence_required':a.require_decoder_evidence,'source_transport_provenance':json.loads((ROOT/'results/native-cas-sdk-source-provenance.json').read_text()),'commands':commands,'system_modified':False,'GPU_qualification_pending':True},indent=2)+'\n')
print('Module ready; GPU qualification pending',str(sdk))
