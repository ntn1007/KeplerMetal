#!/usr/bin/env python3
"""Freeze and run the integrated native-CAS/CPU-ICB client on this iMac."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--mode',choices=['register','prepare','execute','native'],default='prepare');a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();(out/'outputs').mkdir();commands=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(argv,label):
 r=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':argv,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,r.returncode,flush=True);assert r.returncode==0,r.stderr[-3000:]
sources=[]
for folder,name in [('src','KeplerCPUICB.h'),('src','KeplerCPUICB.mm'),('src','KeplerNativeCommands.h'),('src','KeplerNativeCommands.mm'),('src','KeplerNativeCAS.h'),('src','KeplerNativeCAS.mm'),('src','KeplerNativeCASAdapter.inc'),('src','KeplerProgramImport.h'),('src','cpu_icb_native_cas_manifest.json'),('tools','cpu_icb_native_cas_probe.mm')]:
 f=out/name;shutil.copyfile(ROOT/folder/name,f);sources.append(f)
assets=out/'assets';shutil.copytree(ROOT/'results/native-cas-sdk-build-20261014-02/KeplerNativeCAS/assets',assets)
inp={'source_hashes':{p.name:sha(p) for p in sources},'assets_SHA256':{p.name:sha(p) for p in assets.iterdir()},'Git_commit':None,'Qwen_job_ids':[],'system_modified':False};(out/'inputs.json').write_text(json.dumps(inp,indent=2)+'\n')
objects=[]
for name in ['KeplerCPUICB','KeplerNativeCommands','KeplerNativeCAS']:
 obj=out/(name+'.o');run(['clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc' if name=='KeplerNativeCAS' else '-fobjc-arc','-I',str(out),'-c',str(out/(name+'.mm')),'-o',str(obj)],'compile-'+name);objects.append(obj)
exe=out/'cpu_icb_native_cas_probe';run(['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-I',str(out),str(out/'cpu_icb_native_cas_probe.mm'),*[str(p) for p in objects],'-framework','Metal','-framework','Foundation','-o',str(exe)],'client')
run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(out/'execution'),'--timeout','30','--',str(assets),str(out/'cpu_icb_native_cas_manifest.json'),str(out/'outputs'),sha(out/'cpu_icb_native_cas_manifest.json'),a.mode],'observe')
m=json.loads((out/'execution/manifest.json').read_text());assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'];d=json.loads((out/'execution/execution.stdout').read_text());(out/'results.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'mode':d['mode'],'trials':len(d['runs']),'scope_restored':d['scope_restored'],'pid':m['pid']}))
