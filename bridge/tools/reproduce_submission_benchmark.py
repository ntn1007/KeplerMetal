#!/usr/bin/env python3
from pathlib import Path
import argparse,datetime,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--library-input',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--modes',type=int,choices=[2,3],default=2);a=p.parse_args()
base=a.library_input.resolve();out=a.out.resolve();base.relative_to(ROOT/'results');out.relative_to(ROOT/'results');assert not out.exists();out.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
reference_library=base/'resource_sync_probe.metallib';ref=json.loads((base/'manifest.json').read_text());assert sha(reference_library)==ref['library_sha256']
library=out/'submission_benchmark.metallib'
system={s:sha(Path(s)) for s in ref['system_after']};commands=[]
source=out/'submission_benchmark.mm';shutil.copyfile(ROOT/'tools/submission_benchmark.mm',source)
shader=out/'submission_benchmark.metal';shutil.copyfile(ROOT/'src/submission_benchmark.metal',shader)
for tool in [Path(__file__),ROOT/'tools/verify_submission_benchmark.py']:shutil.copyfile(tool,out/tool.name)
probe=out/'submission_benchmark'
def run(cmd,label,timeout):
 r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=timeout)
 (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr)
 commands.append({'label':label,'argv':cmd,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 print(label,r.returncode,flush=True);assert r.returncode==0,r.stderr[-4000:];return r
run(['xcrun','-sdk','macosx','metal','-std=macos-metal2.0','-c',str(shader),'-o',str(out/'submission_benchmark.air')],'metal-compile',50)
run(['xcrun','-sdk','macosx','metallib',str(out/'submission_benchmark.air'),'-o',str(library)],'metallib-link',50)
run(['xcrun','clang++','-O2','-std=c++17','-fobjc-arc',str(source),'-framework','Foundation','-framework','Metal','-o',str(probe)],'compile',50)
outputs=out/'outputs';outputs.mkdir();execution=out/'execution'
run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(probe),'--out',str(execution),'--timeout','50','--',str(library),str(outputs)]+(['three_modes'] if a.modes==3 else []),'execute',58)
process=json.loads((execution/'manifest.json').read_text());assert not process['authoritative_ps_status'] and not process['SIGKILL_requested']
result=json.loads((execution/'execution.stdout').read_text());assert result['passed']
(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
after={s:sha(Path(s)) for s in system};assert system==after
(out/'manifest.json').write_text(json.dumps({'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'system_before':system,'system_after':after,
 'library_path':str(library),'library_sha256':sha(library),'source_hashes':{p.name:sha(p) for p in out.glob('*.py')}|{source.name:sha(source),shader.name:sha(shader)},
 'process':process,'mode_count':a.modes,'measurements':'Wall clock plus caller-thread and process CPU; no GPU-exclusive timing, fixed identical workload.'},indent=2)+'\n')
