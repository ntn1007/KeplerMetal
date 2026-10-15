#!/usr/bin/env python3
"""Select observed native allocation profiles and freeze the preserving-import client."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ['out','native-build','observations','programs','library']:p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();out=a.out.resolve();out.relative_to(ROOT/'results');out.mkdir(exist_ok=False)
    native=a.native_build.resolve();obs=a.observations.resolve();programs=a.programs.resolve();lib=a.library.resolve()
    ni=json.loads((native/'inputs.json').read_text());od=json.loads((obs/'observations.json').read_text());pm=json.loads((programs/'manifest.json').read_text());lm=json.loads((lib/'manifest.json').read_text())
    assert json.loads((obs/'status.json').read_text())['status']=='PASS'
    assert od['native_build_inputs_SHA256']==sha(native/'inputs.json')==pm['native_inputs_SHA256']
    assert sha(native/'control_flow.metal')==pm['MSL_SHA256']and sha(native/'control_flow.air')==pm['AIR_SHA256']
    assert sha(lib/'libKeplerMetal.a')==lm['static_library_SHA256']
    for n,h in ni['assets_SHA256'].items():assert sha(native/'assets'/n)==h
    shutil.copytree(native/'assets',out/'assets');shutil.copytree(native/'runtime',out/'runtime')
    for row in od['records']:
        w=row['metadata_words'];v=row['variant_words_0_128'];assert w[9]==w[12]*64+w[11]and w[12]==w[13]and not w[35]
        assert v[10]==((w[12]+15)&~15)*64+((w[11]+511)&~511)+512
        assert v[12]==w[7] and v[14]==w[14]
        code=obs/row['function']/'capture/native.sass';assert sha(code)==row['code_SHA256'];shutil.copyfile(code,out/'assets'/(row['function']+'-native.sass'))
    selected=[]
    for row in pm['programs']:
        if row['source_depth']>40:continue
        info=row['info'];assert info['code_bytes']<=65536 and not info['shared_bytes']
        choices=[x for x in od['records']if x['metadata_words'][7]>=info['registers']and x['metadata_words'][12]>=info['scratch_bytes']and ((x['metadata_words'][11]+511)&~511)>=info['crs_bytes']]
        assert choices,('No observed native allocation fits',row['name'],info)
        carrier=min(choices,key=lambda x:x['source_depth'])
        profile={k:carrier[k]for k in ['function','source_depth','metadata_words','variant_words_0_128','code_SHA256','code_bytes']}
        name=row['name'];assert sha(programs/name/'program.sass')==row['code_SHA256'];shutil.copyfile(programs/name/'program.sass',out/'assets'/(name+'.sass'))
        item={'program_info':info,'code_SHA256':row['code_SHA256'],'carrier':profile,'allocation_policy':'Preserve all native metadata except instruction count; no reserve or GPR changes'}
        (out/'assets'/(name+'.json')).write_text(json.dumps(item,indent=2)+'\n');selected.append({'program':name,'carrier':carrier['function'],'scratch_required':info['scratch_bytes'],'CRS_required':info['crs_bytes'],'native_frame':profile['metadata_words'][12],'native_control_field':profile['metadata_words'][11]})
    shutil.copyfile(ROOT/'tools/control_flow_probe.mm',out/'control_flow_probe.mm')
    cmd=list(map(str,['clang++','-arch','x86_64','-O2','-std=c++17','-fobjc-arc','-DKP_CONTROL_IMPORT=1',out/'control_flow_probe.mm',lib/'libKeplerMetal.a','-Wl,-ObjC','-framework','Metal','-framework','Foundation','-o',out/'application']))
    r=subprocess.run(cmd,capture_output=True,text=True,timeout=60);(out/'host.stdout').write_text(r.stdout);(out/'host.stderr').write_text(r.stderr);(out/'commands.json').write_text(json.dumps([{'argv':cmd,'exit_code':r.returncode}],indent=2)+'\n');assert not r.returncode,r.stderr[-3000:]
    d={'source_hashes':{'control_flow_probe.mm':sha(out/'control_flow_probe.mm')},'assets_SHA256':{f.name:sha(f)for f in(out/'assets').iterdir()},'runtime_SHA256':{f.name:sha(f)for f in(out/'runtime').iterdir()},'executable_SHA256':sha(out/'application'),'static_library_SHA256':sha(lib/'libKeplerMetal.a'),'library_manifest_SHA256':sha(lib/'manifest.json'),'programs_manifest_SHA256':sha(programs/'manifest.json'),'native_observations_SHA256':sha(obs/'observations.json'),'source_generator_SHA256':sha(__file__),'profiles':selected,'GPU_execution':False}
    (out/'inputs.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({'status':'PASS','library_SHA256':d['static_library_SHA256'],'profiles':selected},indent=2))

if __name__=='__main__':main()
