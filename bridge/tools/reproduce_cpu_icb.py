#!/usr/bin/env python3
from pathlib import Path
import argparse,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();commands=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(argv,label):
 r=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':argv,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,r.returncode,flush=True);assert r.returncode==0,r.stderr[-4000:]
sources=[]
for sub,name in [('src','KeplerCPUICB.h'),('src','KeplerCPUICB.mm'),('src','KeplerNativeCommands.h'),('src','KeplerNativeCommands.mm'),('tools','cpu_icb_probe.mm')]:
 f=out/name;f.write_bytes((ROOT/sub/name).read_bytes());sources.append(f)
library=out/'indirect_compute_probe.metallib';library.write_bytes((ROOT/'results/indirect-compute-native-qualified'/library.name).read_bytes());exe=out/'cpu_icb_probe'
(out/Path(__file__).name).write_bytes(Path(__file__).read_bytes());(out/'inputs.json').write_text(json.dumps({'source_hashes':{x.name:sha(x) for x in sources},'library_SHA256':sha(library),'Git_commit':None,'Qwen_job_ids':[],'system_modified':False},indent=2)+'\n')
run(['clang++','-O2','-std=c++17','-fobjc-arc','-I',str(out),str(out/'cpu_icb_probe.mm'),str(out/'KeplerCPUICB.mm'),str(out/'KeplerNativeCommands.mm'),'-framework','Metal','-framework','Foundation','-o',str(exe)],'build')
dest=out/'outputs';dest.mkdir();execution=out/'execution';run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(execution),'--timeout','30','--',str(library),str(dest),'execute' if a.execute else 'prepare'],'observe')
process=json.loads((execution/'manifest.json').read_text());assert process['exit_code']==0 and not process['SIGKILL_requested'] and not process['authoritative_ps_status'];data=json.loads((execution/'execution.stdout').read_text());(out/'results.json').write_text(json.dumps(data,indent=2)+'\n');assert data['passed'];print(json.dumps({'mode':data['mode'],'runs':len(data['runs']),'scope_restored':data['scope_restored'],'all_children_terminal':True},indent=2))
