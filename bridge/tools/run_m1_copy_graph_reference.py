#!/usr/bin/env python3
"""Run only on the M1 source bundle; no Kepler binary or system installation."""
from pathlib import Path
import hashlib, json, shutil, subprocess, sys

ROOT=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
manifest=json.loads((ROOT/'FILE_MANIFEST.json').read_text())
for e in manifest['files']:
    assert sha(ROOT/e['path'])==e['SHA256'] and (ROOT/e['path']).stat().st_size==e['bytes']
assert subprocess.check_output(['uname','-m'],text=True).strip()=='arm64'
out=ROOT/'build';out.mkdir(exist_ok=False);history=[]
def run(label,argv):
    r=subprocess.run(argv,capture_output=True,text=True,timeout=45)
    (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr)
    history.append({'label':label,'argv':argv,'exit_code':r.returncode})
    (out/'commands.json').write_text(json.dumps(history,indent=2)+'\n')
    assert r.returncode==0,(label,r.stderr[-2000:])
run('metal',['xcrun','-sdk','macosx','metal','-std=macos-metal2.3','-c',str(ROOT/'cpu_icb_profiles.metal'),'-o',str(out/'library.air')])
run('metallib',['xcrun','-sdk','macosx','metallib',str(out/'library.air'),'-o',str(out/'library.metallib')])
run('host',['clang++','-arch','arm64','-O2','-std=c++17','-fobjc-arc','-DKP_GPU_COPY_NATIVE=1','-I',str(ROOT),str(ROOT/'cpu_icb_copy_graph_client.mm'),'-framework','Metal','-framework','Foundation','-o',str(out/'application')])
nm=subprocess.check_output(['nm','-u',str(out/'application')],text=True)
assert 'KPCPUICB' not in nm;(out/'nm.txt').write_text(nm)
sources=['cpu_icb_copy_graph_client.mm','KeplerCPUICB.h']
inputs={'source_SHA256':{n:sha(ROOT/n) for n in sources},'library_SHA256':sha(out/'library.metallib'),'executable_SHA256':sha(out/'application'),'runtime_SHA256':{n:sha(ROOT/n) for n in ['lab_gpu_reservation.py','run_sdk_host.py']},'core_source_compilations':0,'native_reference':True,'macOS':subprocess.check_output(['sw_vers'],text=True),'SDK':subprocess.check_output(['xcrun','--show-sdk-version'],text=True).strip()}
(out/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
from run_sdk_host import run_host
from verify_cpu_icb_copy_graph import verify
progress=[]
for local,groups in [(32,3),(33,3),(128,5)]:
    for mode in ['prepare_chain','chain','range','chain_completed','range_completed','no_chain','no_range']:
        case=f'{mode}-l{local}-g{groups}';target=ROOT/'results'/case
        target.mkdir(parents=True,exist_ok=False);(target/'outputs').mkdir()
        for n in ['application','library.metallib','inputs.json']:shutil.copyfile(out/n,target/n)
        for n in sources:shutil.copyfile(ROOT/n,target/n)
        (target/'application').chmod(0o755)
        m=run_host(target/'application',target/'execution',[str(target/'library.metallib'),str(target/'outputs'),mode,str(local),str(groups)],ROOT)
        d=json.loads((target/'execution/execution.stdout').read_text());(target/'results.json').write_text(json.dumps(d,indent=2)+'\n')
        v=verify(target);(target/'independent-verification.json').write_text(json.dumps(v,indent=2)+'\n')
        progress.append({'case':case,'PID':m['pid'],'status':v['status'],'exact_words':v['exact_uint32_words']})
        (ROOT/'results/history.json').write_text(json.dumps(progress,indent=2)+'\n')
        print(case,v['status'],v['exact_uint32_words'],flush=True)
