#!/usr/bin/env python3
"""Build the SAME dataflow client and MSL using native Apple M1 command buffers."""
from pathlib import Path
import hashlib,json,subprocess
ROOT=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
for f in json.loads((ROOT/'FILE_MANIFEST.json').read_text())['files']:assert sha(ROOT/f['path'])==f['SHA256']
assert subprocess.check_output(['uname','-m'],text=True).strip()=='arm64'
out=ROOT/'build';out.mkdir(exist_ok=False);(out/'assets').mkdir();commands=[]
def run(args,label):
 args=[str(x)for x in args];r=subprocess.run(args,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':args,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert not r.returncode,r.stderr[-3000:]
for name,src in [('consumer','cpu_icb_dependency.metal'),('producer','gpu_command_frontend_dataflow.metal')]:
 run(['xcrun','metal','-std=macos-metal2.3','-c',ROOT/src,'-o',out/(name+'.air')],name+'-metal');run(['xcrun','metallib',out/(name+'.air'),'-o',out/'assets'/(name+'.metallib')],name+'-metallib')
(out/'assets/consumer.json').write_bytes((ROOT/'cpu_icb_dependency_manifest.json').read_bytes())
run(['clang++','-arch','arm64','-O2','-std=c++17','-fobjc-arc','-DKP_DATAFLOW_NATIVE=1','-I',ROOT,ROOT/'command_ir_dataflow_client.mm','-framework','Metal','-framework','Foundation','-o',out/'application'],'host')
from run_sdk_host import run_host
history=[]
for mode in ['no_producer','barrier','no_consumer']:
 target=ROOT/'results'/mode;target.mkdir(parents=True);(target/'outputs').mkdir();m=run_host(out/'application',target/'execution',[str(out/'assets'),str(target/'outputs'),mode],ROOT);d=json.loads((target/'execution/execution.stdout').read_text());(target/'results.json').write_text(json.dumps(d,indent=2)+'\n');assert d['native_reference']and len(d['runs'])==4 and all(x['command_status']==4 for x in d['runs']);history.append({'mode':mode,'PID':m['pid'],'exit_code':m['exit_code']});(ROOT/'results/history.json').write_text(json.dumps(history,indent=2)+'\n');print(mode,'PASS',flush=True)
(ROOT/'results/provenance.json').write_text(json.dumps({'macOS':subprocess.check_output(['sw_vers'],text=True),'architecture':'arm64','SDK':subprocess.check_output(['xcrun','--show-sdk-version'],text=True).strip(),'source_manifest_SHA256':sha(ROOT/'FILE_MANIFEST.json'),'executable_SHA256':sha(out/'application'),'system_modified':False,'job_ids':[]},indent=2)+'\n')
