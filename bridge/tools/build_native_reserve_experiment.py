#!/usr/bin/env python3
"""Freeze an upward-only native reserve experiment with exact incoming certificates."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['out','native-build','observations']:p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--reserve',choices=['0','round','4096'],required=True);mode=p.add_mutually_exclusive_group();mode.add_argument('--contracts',action='store_true');mode.add_argument('--lifetime',action='store_true');a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
    native=a.native_build.resolve();obs=a.observations.resolve();ni=json.loads((native/'inputs.json').read_text());od=json.loads((obs/'observations.json').read_text());assert od['native_build_inputs_SHA256']==sha(native/'inputs.json')
    for n,h in ni['assets_SHA256'].items():assert sha(native/'assets'/n)==h
    shutil.copytree(native/'assets',out/'assets');shutil.copytree(native/'runtime',out/'runtime')
    certificates={}
    for row in od['records']:
        assert sha(obs/row['function']/'capture/native.sass')==row['code_SHA256'];certificates[row['function']]={'metadata_words':row['metadata_words'],'code_SHA256':row['code_SHA256']}
    config={'variant':ni.get('variant','nested'),'entry_witness':ni.get('entry_witness',False),'depths':[r['source_depth']for r in od['records']],'certificates':certificates,'control_reserve':a.reserve if a.reserve=='round'else int(a.reserve)}
    (out/'assets/control_flow_config.json').write_text(json.dumps(config,indent=2)+'\n')
    host='native_reserve_contract_probe.mm'if a.contracts else'native_reserve_lifetime_probe.mm'if a.lifetime else'control_flow_probe.mm'
    sources=[host,'NativeControlReserveExperiment.mm']
    if a.lifetime:sources.append('control_flow_probe.mm')
    for n in sources:shutil.copyfile(ROOT/'tools'/n,out/n)
    commands=[]
    for name,cmd in [('module',['clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-c',out/'NativeControlReserveExperiment.mm','-o',out/'reserve.o']),('host',['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-DKP_NATIVE_RESERVE_EXPERIMENT=1',out/host,out/'reserve.o','-framework','Foundation','-framework','Metal','-o',out/'application'])]:
        cmd=list(map(str,cmd));r=subprocess.run(cmd,capture_output=True,text=True,timeout=60);(out/(name+'.stdout')).write_text(r.stdout);(out/(name+'.stderr')).write_text(r.stderr);commands.append({'label':name,'argv':cmd,'exit_code':r.returncode});(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');assert not r.returncode,r.stderr[-3000:];print(name,'PASS',flush=True)
    d={'source_hashes':{n:sha(out/n)for n in sources},'assets_SHA256':{f.name:sha(f)for f in(out/'assets').iterdir()},'runtime_SHA256':{f.name:sha(f)for f in(out/'runtime').iterdir()},'executable_SHA256':sha(out/'application'),'native_build_inputs_SHA256':sha(native/'inputs.json'),'observations_SHA256':sha(obs/'observations.json'),'source_generator_SHA256':sha(__file__),'reserve_mode':a.reserve,'contract_probe':a.contracts,'lifetime_probe':a.lifetime,'GPU_execution':False,'scope':'Native GPU code unchanged; only metadata reserve words9/11 can increase'}
    (out/'inputs.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'status':'PASS','reserve':a.reserve}))
if __name__=='__main__':main()
