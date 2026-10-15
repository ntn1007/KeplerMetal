#!/usr/bin/env python3
"""Compile and run the native M1 public-MSL command runtime reference."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for e in json.loads((ROOT/'FILE_MANIFEST.json').read_text())['files']:assert sha(ROOT/e['path'])==e['SHA256']
assert subprocess.check_output(['uname','-m'],text=True).strip()=='arm64'
out=ROOT/'build';out.mkdir(exist_ok=False);(out/'assets').mkdir();commands=[]
def run(args,label):
 r=subprocess.run([str(x)for x in args],capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':[str(x)for x in args],'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert not r.returncode,r.stderr[-3000:]
for name,source in [('combined_shared','cpu_icb_combined_shared.metal'),('runtime_producer','gpu_command_frontend_runtime.metal')]:
 run(['xcrun','metal','-std=macos-metal2.3','-c',ROOT/source,'-o',out/(name+'.air')],name+'-metal')
 run(['xcrun','metallib',out/(name+'.air'),'-o',out/'assets'/(name+'.metallib')],name+'-metallib')
run(['clang++','-arch','arm64','-O2','-std=c++17','-fobjc-arc','-DKP_SELECT_NATIVE=1','-I',ROOT,ROOT/'gpu_command_bindings_client.mm','-framework','Metal','-framework','Foundation','-o',out/'application'],'host')
from run_sdk_host import run_host
history=[]
for mode in ['basic','barrier','clear','copy','reset','no_producer','split']:
 target=ROOT/'results'/mode;target.mkdir(parents=True);(target/'outputs').mkdir();m=run_host(out/'application',target/'execution',[str(out/'assets'),str(target/'outputs'),mode],ROOT)
 d=json.loads((target/'execution/execution.stdout').read_text());(target/'results.json').write_text(json.dumps(d,indent=2)+'\n');assert d['native_reference'] and len(d['runs'])==3 and all(r['command_status']==4 for r in d['runs']);history.append({'mode':mode,'PID':m['pid'],'exit_code':m['exit_code']});(ROOT/'results/history.json').write_text(json.dumps(history,indent=2)+'\n');print(mode,'PASS',flush=True)
(ROOT/'results/provenance.json').write_text(json.dumps({'architecture':'arm64','macOS':subprocess.check_output(['sw_vers'],text=True),'SDK':subprocess.check_output(['xcrun','--show-sdk-version'],text=True).strip(),'source_manifest_SHA256':sha(ROOT/'FILE_MANIFEST.json'),'executable_SHA256':sha(out/'application'),'job_ids':[],'system_modified':False},indent=2)+'\n')
