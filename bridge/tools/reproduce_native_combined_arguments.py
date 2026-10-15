#!/usr/bin/env python3
"""Freeze/build fragment argument-buffer ABI and uncommitted command observation."""
from pathlib import Path
import argparse,hashlib,json,subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--execute',action='store_true');a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir();commands=[]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run(argv,label):
    r=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,timeout=45);(out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':argv,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(label,r.returncode,flush=True);assert r.returncode==0,r.stderr[-2500:]
sources=[]
for folder,n in [('src','combined_render_resources.metal'),('src','graphics_reference.metal'),('tools','native_combined_arguments_capture.mm')]:
    f=out/n;f.write_bytes((ROOT/folder/n).read_bytes());sources.append(f)
(out/Path(__file__).name).write_bytes(Path(__file__).read_bytes());air=out/'combined_render_resources.air';library=out/'combined_render_resources.metallib'
run(['xcrun','-sdk','macosx','metal','-std=macos-metal2.4','-c',str(out/'combined_render_resources.metal'),'-o',str(air)],'air')
run(['xcrun','-sdk','macosx','metallib',str(air),'-o',str(library)],'metallib')
(out/'inputs.json').write_text(json.dumps({'source_hashes':{f.name:sha(f) for f in sources},'library_SHA256':sha(library),'Git_commit':None,'Qwen_job_ids':[],'system_modified':False},indent=2)+'\n')
exe=out/'native_combined_arguments_capture';run(['clang++','-O2','-std=c++17','-fobjc-arc',str(out/'native_combined_arguments_capture.mm'),'-framework','Metal','-framework','Foundation','-o',str(exe)],'build');raw=out/'outputs';raw.mkdir()
run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(exe),'--out',str(out/'execution'),'--timeout','30','--',str(library),str(raw)]+(['execute'] if a.execute else []),'observe')
m=json.loads((out/'execution/manifest.json').read_text());assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'];d=json.loads((out/'execution/execution.stdout').read_text());assert d['committed']==a.execute and not d['native_memory_modified'] and d['GPU_user_submissions']==(3 if a.execute else 0);(out/'capture.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'rows':len(d['rows']),'library_SHA256':sha(library),'all_children_terminal':True},indent=2))
