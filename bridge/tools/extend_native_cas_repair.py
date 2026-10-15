#!/usr/bin/env python3
"""Test the already-validated native repair at the physical 1024-thread limit."""
from pathlib import Path
import argparse, datetime, hashlib, json, shutil, subprocess
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
a=p.parse_args();base=a.input.resolve();out=a.out.resolve();base.relative_to(ROOT/'results');out.relative_to(ROOT/'results')
assert not out.exists();out.mkdir();commands=[];records=[]
def sha(x):return hashlib.sha256(x.read_bytes()).hexdigest()
manifest=json.loads((base/'manifest.json').read_text())
for key in ['replay','repaired','trampoline']:assert sha(base/('native-'+key+'.sass'))==manifest['code_sha256'][key]
source=out/'air_cas_probe.mm';shutil.copyfile(ROOT/'tools/air_cas_probe.mm',source)
library=base/'libPinnedNativeCASImport.dylib';probe=out/'air_cas_probe'
def run(cmd,label,allowed=(0,)):
 r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=50)
 (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr)
 commands.append({'label':label,'argv':cmd,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 print(label,r.returncode,flush=True);assert r.returncode in allowed,r.stderr;return r
run(['clang++','-O2','-std=c++17','-fno-objc-arc','-DPINNED_NATIVE_CAS_IMPORT',str(source),
     '-I'+str(ROOT/'src'),str(library),'-framework','Metal','-framework','Foundation','-o',str(probe)],'build-probe')
for variant in [0,1]:
 plan={'mode':'native_repaired','space':'threadgroup','local':1024,'groups':3,'contended':True,'variant':variant,
       'library':str(ROOT/'results/cas-lowering-final/threadgroup/test.metallib'),
       'code':str(base/'native-repaired.sass'),'original_code':str(base/'native-replay.sass')}
 name=f'native_repaired-l1024-g3-v{variant}';path=out/(name+'.plan.json');path.write_text(json.dumps(plan,indent=2)+'\n')
 outputs=out/(name+'-outputs');outputs.mkdir();execution=out/(name+'-execution')
 run(['python3',str(ROOT/'tools/run_signed_probe.py'),'--exe',str(probe),'--out',str(execution),'--timeout','20',
      '--',str(path),str(outputs)],name)
 process=json.loads((execution/'manifest.json').read_text());assert not process['authoritative_ps_status']
 result=json.loads((execution/'execution.stdout').read_text());assert result['passed'] and result['pipeline_max_threads']>=1024
 records.append({'name':name,'plan':plan,'process':process,'result':result,'execution':str(execution)})
 (out/'results.json').write_text(json.dumps(records,indent=2)+'\n')
# Store exact immutable program references in the verifier's expected layout.
for name in ['native-replay.sass','native-repaired.sass','native-trampoline.sass']:shutil.copyfile(base/name,out/name)
(out/'manifest.json').write_text(json.dumps({'captured_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'base':str(base),'system_before':manifest['system_after'],
 'system_after':{s:sha(Path(s)) for s in manifest['system_after']},'source_sha256':sha(source),'library_sha256':sha(library),
 'scope':'Incremental native shader repair qualification, 1024 lanes/group and 3 groups; no repeat of smaller successful cases.'},indent=2)+'\n')
print('Completed new 1024-thread cases',len(records))
