#!/usr/bin/env python3
"""Separate MSL frontend and native pipeline acceptance for GPU-encoded ICB.
The shader is never dispatched; an ICB is never created or faked.
"""
from pathlib import Path
import argparse,datetime,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
commands=[]
def run(cmd,label,allowed=(0,)):
 r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=45)
 (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr)
 commands.append({'label':label,'argv':cmd,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 print(label,r.returncode,flush=True)
 if r.returncode not in allowed:raise SystemExit(r.stderr[-4000:] or str(r.returncode))
 return r
source=out/'test.metal';source.write_text('''#include <metal_stdlib>
using namespace metal;
struct Container { command_buffer commands [[id(0)]]; };
kernel void test(device Container *container [[buffer(0)]],uint i [[thread_position_in_grid]]) {
    render_command command(container->commands,i);
    command.draw_primitives(primitive_type::triangle,0,3,1,0);
}
''')
air=out/'test.air';library=out/'test.metallib'
run(['xcrun','metal','-std=macos-metal2.4','-fno-fast-math','-c',str(source),'-o',str(air)],'frontend')
run(['xcrun','metallib',str(air),'-o',str(library)],'library')
execution=out/'execution';capture=out/'capture'
run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(ROOT/'build/compiler_output_trace'),
     '--out',str(execution),'--timeout','20','--',str(library),str(capture),'compute','test'],'native-pipeline',(0,4,124))
process=json.loads((execution/'manifest.json').read_text())
if process['authoritative_ps_status'] or process['SIGKILL_requested']:raise SystemExit('HALT: child not cleanly terminal; do not restart')
observed=json.loads((execution/'execution.stdout').read_text());assert not observed['gpu_dispatch']
shutil.copyfile(Path(__file__),out/Path(__file__).name)
summary={'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'frontend':'PASS','MSL':'macos-metal2.4',
 'native_pipeline':'PASS' if observed['pipeline_created'] else 'BLOCKED','observation':observed,'GPU_dispatch':False,
 'ICB_created':False,'child_terminal':True,'source_hashes':{p.name:sha(p) for p in [source,air,library,out/Path(__file__).name]},
 'capture_tool':{'path':str(ROOT/'build/compiler_output_trace'),'sha256':sha(ROOT/'build/compiler_output_trace')},
 'scope':'Compiler/pipeline acceptance only; no GPU-generated ICB or indirect execution qualified.'}
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps(summary,indent=2))
