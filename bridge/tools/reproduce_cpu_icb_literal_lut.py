#!/usr/bin/env python3
from pathlib import Path
import argparse,hashlib,json,subprocess,shutil,platform
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--mode',choices=['prepare','execute','native','reject-size','reject-unqualified'],default='prepare');p.add_argument('--reuse-host-from',type=Path);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();(out/'outputs').mkdir();commands=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(argv,label):
 r=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=55);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':argv,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,r.returncode,flush=True);assert r.returncode==0,r.stderr[-2500:]
files=[]
for folder,n in [('src','KeplerCPUICB.h'),('src','KeplerCPUICB.mm'),('src','KeplerNativeCommands.h'),('src','KeplerNativeCommands.mm'),('src','cpu_icb_literal_lut.metal'),('src','cpu_icb_literal_lut_manifest.json'),('src','cpu_icb_literal_lut_values.json'),('tools','cpu_icb_literal_lut_probe.mm')]:
 f=out/n;f.write_bytes((ROOT/folder/n).read_bytes());files.append(f)
lib=out/'literal_lut.metallib';lib.write_bytes((ROOT/'results/native-literal-bank-passive-20261014/literal_lut.metallib').read_bytes())
profile=out/'used-manifest.json';d=json.loads((out/'cpu_icb_literal_lut_manifest.json').read_text())
if a.mode=='reject-size':d['functions'][2]['native_literal_bank_0']['bytes']=256
if a.mode=='reject-unqualified':d['functions'][2]['native_literal_bank_0']['bytes']=384
profile.write_text(json.dumps(d,indent=2)+'\n')
toolchain={'clang':subprocess.check_output(['clang++','--version'],text=True),'SDK':subprocess.check_output(['xcrun','--sdk','macosx','--show-sdk-version'],text=True).strip(),'host_architecture':platform.machine(),'flags':['-O2','-std=c++17','-fobjc-arc','-framework Metal','-framework Foundation']}
inputs={'source_hashes':{f.name:sha(f) for f in files},'library_SHA256':sha(lib),'used_manifest_SHA256':sha(profile),'toolchain':toolchain,'Git_commit':None,'Qwen_job_ids':[]}
exe=out/'cpu_icb_literal_lut_probe'
if a.reuse_host_from:
 old=a.reuse_host_from.resolve();old.relative_to(ROOT/'results');prior=json.loads((old/'inputs.json').read_text());m=json.loads((old/'execution/manifest.json').read_text());original=old/'cpu_icb_literal_lut_probe'
 assert prior['source_hashes']==inputs['source_hashes'] and prior['library_SHA256']==inputs['library_SHA256'] and prior['toolchain']==toolchain and sha(original)==m['original_binary_sha256']
 assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
 shutil.copyfile(original,exe);exe.chmod(0o755);assert sha(exe)==m['original_binary_sha256'];inputs['host_reused_from']=str(old);inputs['reused_original_binary_SHA256']=sha(exe);inputs['reuse_scope']='Explicit pinned executable reuse, not a general SDK/header dependency cache'
else:
 run(['clang++','-O2','-std=c++17','-fobjc-arc','-I',str(out),str(out/'cpu_icb_literal_lut_probe.mm'),str(out/'KeplerCPUICB.mm'),str(out/'KeplerNativeCommands.mm'),'-framework','Metal','-framework','Foundation','-o',str(exe)],'build')
(out/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(out/'execution'),'--timeout','30','--',str(lib),str(profile),str(out/'outputs'),a.mode],'observe')
m=json.loads((out/'execution/manifest.json').read_text());assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and m['GPU_reservation']['state']=='terminal'
d=json.loads((out/'execution/execution.stdout').read_text());(out/'results.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'mode':a.mode,'trials':len(d.get('runs',[])),'pid':m['pid'],'scope_restored':d['scope_restored']}))
