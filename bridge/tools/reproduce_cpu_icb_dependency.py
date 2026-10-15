#!/usr/bin/env python3
from pathlib import Path
import argparse,hashlib,json,subprocess
from contextlib import nullcontext
ROOT=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--mode',choices=['prepare','execute','native'],default='prepare');p.add_argument('--profile-phases',action='store_true');a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();(out/'outputs').mkdir();commands=[]
timing=None
if a.profile_phases:
 from lab_phase_timing import PhaseLog
 timing=PhaseLog(out/'workflow-phases.json',[Path(__file__),ROOT/'tools/lab_phase_timing.py',ROOT/'tools/run_signed_probe.py'])
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(argv,label):
 with timing.phase(label,argv=argv) if timing else nullcontext({}) as measured:
  r=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':argv,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,r.returncode,flush=True);measured.update(exit_code=r.returncode,stdout_bytes=len(r.stdout.encode()),stderr_bytes=len(r.stderr.encode()));assert r.returncode==0,r.stderr[-3000:]
sources=[]
for folder,n in [('src','KeplerCPUICB.h'),('src','KeplerCPUICB.mm'),('src','KeplerNativeCommands.h'),('src','KeplerNativeCommands.mm'),('src','cpu_icb_dependency.metal'),('src','cpu_icb_dependency_manifest.json'),('tools','cpu_icb_dependency_probe.mm')]:f=out/n;f.write_bytes((ROOT/folder/n).read_bytes());sources.append(f)
lib=out/'dependency.metallib';lib.write_bytes((ROOT/'results/icb-dependency-native-passive/dependency.metallib').read_bytes());(out/'inputs.json').write_text(json.dumps({'source_hashes':{p.name:sha(p) for p in sources},'library_SHA256':sha(lib),'Git_commit':None,'Qwen_job_ids':[]},indent=2)+'\n')
exe=out/'cpu_icb_dependency_probe';run(['clang++','-O2','-std=c++17','-fobjc-arc','-I',str(out),str(out/'cpu_icb_dependency_probe.mm'),str(out/'KeplerCPUICB.mm'),str(out/'KeplerNativeCommands.mm'),'-framework','Metal','-framework','Foundation','-o',str(exe)],'build')
run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(out/'execution'),'--timeout','30']+(['--profile-phases'] if a.profile_phases else [])+['--',str(lib),str(out/'cpu_icb_dependency_manifest.json'),str(out/'outputs'),a.mode],'observe')
m=json.loads((out/'execution/manifest.json').read_text());assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'];d=json.loads((out/'execution/execution.stdout').read_text());(out/'results.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'mode':a.mode,'trials':len(d['runs']),'pid':m['pid'],'scope_restored':d['scope_restored']}))
if timing:timing.finish('PASS',child_PID=m['pid'],test_mode=a.mode,user_kernel_main_command_buffers=sum(r['committed'] for r in d['runs']),GPU_oracle_verified=False)
