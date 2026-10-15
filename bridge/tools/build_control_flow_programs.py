#!/usr/bin/env python3
"""Compile the bounded MSL/AIR control programs, accepting CRS for offline analysis only."""
from pathlib import Path
import argparse,hashlib,json,os,shutil,subprocess,time
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--native-build',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
    parent=ROOT/'results/air-local-programs-build-20261015-05';old=json.loads((parent/'manifest.json').read_text());native=a.native_build.resolve();inp=json.loads((native/'inputs.json').read_text())
    assert sha(parent/'compiler')==old['compiler_SHA256']
    for n,h in old['source_SHA256'].items():assert sha(parent/n)==h
    for n,h in old['archives_SHA256'].items():assert sha(ROOT/'build/mesa'/n)==h
    for n,h in inp['source_hashes'].items():assert sha(native/n)==h
    shutil.copytree(parent/'source-fork',out/'source-fork')
    for n in ['air_local_compile.c','KeplerLocalAIRLowering.inc','KeplerResourceABI.h']:shutil.copyfile(parent/n,out/n)
    harness=(out/'air_local_compile.c').read_text();assert harness.count('||binary->info.crs_size||')==1
    # This executable only writes compiler output. No runtime API is changed.
    (out/'air_local_compile.c').write_text(harness.replace('||binary->info.crs_size||','||'))
    for n in ['control_flow.metal','control_flow.air']:shutil.copyfile(native/n,out/n)
    commands=[]
    def run(label,cmd,cwd=ROOT):
        cmd=list(map(str,cmd));env=os.environ.copy();env.pop('NAK_DEBUG',None);start=time.monotonic();r=subprocess.run(cmd,cwd=cwd,env=env,capture_output=True,text=True,timeout=60)
        (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr);commands.append({'label':label,'argv':cmd,'exit_code':r.returncode,'monotonic_seconds':time.monotonic()-start});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
        assert r.returncode==0,(label,r.stderr[-3000:]);print(label,'PASS',flush=True);return r.stdout
    for row in json.loads((parent/'commands.json').read_text()):
        if row['label'] in ['compile-harness','compile-air_nir','compile-bitstream','compile-airir','compile-metallib','link','sign-offline-compiler']:
            run(row['label'],[s.replace(str(parent),str(out))for s in row['argv']],ROOT/'build/mesa')
    records=[]
    for depth in inp['depths']:
        name='depth'+str(depth);case=out/name;case.mkdir();info=json.loads(run('compile-'+name,[out/'compiler',out/'control_flow.air',case,name,32,2]));assert info['sm']==30 and info['source_language']=='MSL/AIR'
        listing=run('decode-'+name,[ROOT/'build/envydis-only/envydis/envydis','-m','gf100','-V','gk104','-i','-n',case/'program.sass']);assert '[unknown'not in listing
        (case/'info.json').write_text(json.dumps(info,indent=2)+'\n');records.append({'name':name,'source_depth':depth,'info':info,'code_SHA256':sha(case/'program.sass')})
        print(name,json.dumps(info),flush=True)
    d={'status':'PASS','GPU_execution':False,'external_CRS_offline_only':True,'compiler_SHA256':sha(out/'compiler'),'builder_SHA256':sha(__file__),'source_SHA256':{str(f.relative_to(out)):sha(f)for f in out.rglob('*')if f.suffix in['.c','.h','.inc','.metal']},'AIR_SHA256':sha(out/'control_flow.air'),'MSL_SHA256':sha(out/'control_flow.metal'),'archives_SHA256':old['archives_SHA256'],'parent_manifest_SHA256':sha(parent/'manifest.json'),'native_inputs_SHA256':sha(native/'inputs.json'),'programs':records,'full_objective_complete':False}
    (out/'manifest.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'status':'PASS','GPU_execution':False,'programs':len(records)}))

if __name__=='__main__':main()
