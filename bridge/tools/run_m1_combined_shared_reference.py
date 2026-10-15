#!/usr/bin/env python3
"""Native M1 reference of the public combined-shared-copy client, source-only bundle."""
from pathlib import Path
import hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parent;sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for e in json.loads((ROOT/'FILE_MANIFEST.json').read_text())['files']:assert sha(ROOT/e['path'])==e['SHA256']
assert subprocess.check_output(['uname','-m'],text=True).strip()=='arm64'
out=ROOT/'build';out.mkdir();(out/'assets').mkdir();history=[]
def run(label,argv):
 r=subprocess.run(argv,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);history.append({'label':label,'argv':argv,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(history,indent=2)+'\n');assert r.returncode==0,r.stderr[-2000:]
run('metal',['xcrun','-sdk','macosx','metal','-std=macos-metal2.3','-c',str(ROOT/'cpu_icb_combined_shared.metal'),'-o',str(out/'library.air')])
run('metallib',['xcrun','-sdk','macosx','metallib',str(out/'library.air'),'-o',str(out/'assets/combined_shared.metallib')])
run('host',['clang++','-arch','arm64','-O2','-std=c++17','-fobjc-arc','-DKP_COMBINED_NATIVE=1','-I',str(ROOT),str(ROOT/'cpu_icb_combined_shared_copy_client.mm'),'-framework','Metal','-framework','Foundation','-o',str(out/'application')])
for n in ['cpu_icb_combined_shared_manifest.json']:shutil.copyfile(ROOT/n,out/'assets'/n)
nm=subprocess.check_output(['nm','-u',str(out/'application')],text=True);assert 'KPCPUICB'not in nm;(out/'nm.txt').write_text(nm)
sources=['cpu_icb_combined_shared_copy_client.mm','KeplerCPUICB.h'];inp={'source_hashes':{n:sha(ROOT/n)for n in sources},'assets_SHA256':{p.name:sha(p)for p in (out/'assets').iterdir()},'executable_SHA256':sha(out/'application'),'runtime_SHA256':{n:sha(ROOT/n)for n in ['lab_gpu_reservation.py','run_sdk_host.py']},'core_source_compilations':0,'native_reference':True,'macOS':subprocess.check_output(['sw_vers'],text=True),'SDK':subprocess.check_output(['xcrun','--show-sdk-version'],text=True).strip()};(out/'inputs.json').write_text(json.dumps(inp,indent=2)+'\n')
from run_sdk_host import run_host
from verify_combined_shared_copy import verify
progress=[]
for mode in ['prepare','chain','range','chain_completed','range_completed','no_second']:
 target=ROOT/'results'/mode;target.mkdir(parents=True);(target/'outputs').mkdir()
 for n in ['application','inputs.json']:shutil.copyfile(out/n,target/n)
 for n in sources:shutil.copyfile(ROOT/n,target/n)
 shutil.copytree(out/'assets',target/'assets');(target/'application').chmod(0o755)
 m=run_host(target/'application',target/'execution',[str(target/'assets'),str(target/'outputs'),mode],ROOT);d=json.loads((target/'execution/execution.stdout').read_text());(target/'results.json').write_text(json.dumps(d,indent=2)+'\n');v=verify(target);(target/'independent-verification.json').write_text(json.dumps(v,indent=2)+'\n');progress.append({'case':mode,'PID':m['pid'],'status':v['status'],'exact_words':v['exact_uint32_words']});(ROOT/'results/history.json').write_text(json.dumps(progress,indent=2)+'\n');print(mode,v['status'],v['exact_uint32_words'],flush=True)
