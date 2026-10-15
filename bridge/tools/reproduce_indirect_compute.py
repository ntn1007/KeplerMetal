#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1];p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();commands=[];cases=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(cmd,label,timeout=50):
 r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=timeout);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':cmd,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,r.returncode,flush=True)
 assert r.returncode==0,r.stderr[-4000:];return r
src=out/'indirect_compute_probe.mm';shader=out/'indirect_compute_probe.metal';shutil.copyfile(ROOT/'tools'/src.name,src);shutil.copyfile(ROOT/'src'/shader.name,shader);(out/Path(__file__).name).write_bytes(Path(__file__).read_bytes())
exe=out/'indirect_compute_probe';lib=out/'indirect_compute_probe.metallib';air=out/'indirect_compute_probe.air'
run(['xcrun','metal','-std=macos-metal2.0','-c',str(shader),'-o',str(air)],'compile-shader');run(['xcrun','metallib',str(air),'-o',str(lib)],'link-shader')
run(['clang++','-O2','-std=c++17','-fobjc-arc',str(src),'-framework','Metal','-framework','Foundation','-o',str(exe)],'build-probe')
for local in [32,33,128]:
 for groups in [1,3,5]:
  for mode in ['direct','GPU_indirect']+(['missing_producer'] if groups!=1 else []):
   name=f'{mode}-l{local}-g{groups}';directory=out/(name+'-outputs');directory.mkdir();execution=out/(name+'-execution')
   run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(execution),'--timeout','20','--',str(lib),str(directory),mode,str(local),str(groups)],name,45)
   process=json.loads((execution/'manifest.json').read_text());assert not process['SIGKILL_requested'] and not process['authoritative_ps_status']
   result=json.loads((execution/'execution.stdout').read_text());cases.append({'name':name,'execution':str(execution),'process':process,'result':result});(out/'results.json').write_text(json.dumps(cases,indent=2)+'\n')
   assert result['passed'] and len(result['runs'])==3 and all(not r['guard_mismatches'] for r in result['runs'])
(out/'manifest.json').write_text(json.dumps({'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_hashes':{p.name:sha(p) for p in [src,shader,out/Path(__file__).name]},'library_sha256':sha(lib),'ICB_implemented':False,'performance_benchmark':False,'system_modified':False},indent=2)+'\n')
print(json.dumps({'cases':len(cases),'all_children_terminal':True},indent=2))
