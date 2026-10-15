#!/usr/bin/env python3
"""Bounded public-API M1 reference; source-only transfer verified before build."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for row in json.loads((ROOT/'FILE_MANIFEST.json').read_text())['files']:assert sha(ROOT/row['path'])==row['SHA256']
assert subprocess.check_output(['uname','-m'],text=True).strip()=='arm64'
out=ROOT/'build';out.mkdir(exist_ok=False);commands=[]
def run(args,label):
 r=subprocess.run([str(x)for x in args],capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':[str(x)for x in args],'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert r.returncode==0,r.stderr[-3000:]
for name,source in [('producer','gpu_command_frontend_methods.metal'),('consumer','command_frontend_reference_consumer.metal')]:
 run(['xcrun','metal','-std=macos-metal2.3','-c',ROOT/source,'-o',out/(name+'.air')],name+'-metal')
 run(['xcrun','metallib',out/(name+'.air'),'-o',out/(name+'.metallib')],name+'-metallib')
run(['clang++','-arch','arm64','-O2','-std=c++17','-fobjc-arc',ROOT/'command_frontend_m1_reference.mm','-framework','Metal','-framework','Foundation','-o',out/'application'],'host')
from run_sdk_host import run_host
results=ROOT/'results';results.mkdir();(results/'outputs').mkdir()
m=run_host(out/'application',results/'execution',[str(out),str(results/'outputs')],ROOT)
d=json.loads((results/'execution/execution.stdout').read_text());(results/'results.json').write_text(json.dumps(d,indent=2)+'\n')
assert len(d['runs'])==12 and d['passed'] and d['native_public_ICB']
(results/'provenance.json').write_text(json.dumps({'architecture':'arm64','macOS':subprocess.check_output(['sw_vers'],text=True),'SDK':subprocess.check_output(['xcrun','--show-sdk-version'],text=True).strip(),'source_manifest_SHA256':sha(ROOT/'FILE_MANIFEST.json'),'executable_SHA256':sha(out/'application'),'job_ids':[],'system_modified':False},indent=2)+'\n')
print(json.dumps({'status':'PASS','device':d['device'],'runs':12,'PID':m['pid']}))
