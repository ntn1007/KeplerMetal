#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build an isolated three-request host using both repeat observer prototypes."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
SOURCES=('metadata_repeat.mm','video_registry_metadata.h','dependency_repeat.mm','video_dependency.h','repeat_gate.h')


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok, why):
    if not ok:raise ValueError(why)
def command(label,argv,out):
    argv=list(map(str,argv));r=subprocess.run(argv,capture_output=True,timeout=90)
    (out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr)
    need(r.returncode==0,label+' failed; inspect retained stderr')
    return {'label':label,'argv':argv,'returncode':r.returncode}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('lab','base','witness-build','diagnostic-build','out'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();lab,base,witness,diagnostic,out=(getattr(a,n).resolve() for n in ('lab','base','witness_build','diagnostic_build','out'))
    for item in (base,witness,diagnostic,out):item.relative_to(lab/'results')
    need(not out.exists() and out.parent.is_dir(),'fresh output required')
    old=json.loads((base/'inputs.json').read_text());w=json.loads((witness/'build.json').read_text());d=json.loads((diagnostic/'build.json').read_text())
    need(w['status']=='PREPARED_ONLY' and w['base_inputs_sha256']==sha(base/'inputs.json') and d['repeat_variant'] and
         d['base_inputs_sha256']==sha(base/'inputs.json') and sha(diagnostic/'registry-repeated.mm')==d['variant_source_sha256'], 'input build differs')
    for name,h in old['frozen'].items():need(sha(base/name)==h,'base input differs: '+name)
    for name,h in w['frozen'].items():need(sha(witness/name)==h,'witness input differs: '+name)
    factory=Path(old['base_build']);need(sha(factory/'inputs.json')==old['base_inputs_SHA256'],'factory inputs differ')
    f=json.loads((factory/'inputs.json').read_text())
    for name,h in f['reused_objects_and_libraries_SHA256'].items():need(sha(name)==h,'linked object differs')
    for name,h in f['new_objects_SHA256'].items():need(sha(factory/name)==h,'factory object differs')
    need(sha(factory/'libVideoFactoryResolver.dylib')==f['resolver_library_SHA256'],'factory library differs')
    out.mkdir();newbase=out/'base';build=out/'build';build.mkdir();shutil.copytree(base,newbase)
    for n in SOURCES:shutil.copyfile(HERE/n,build/n)
    shutil.copyfile(diagnostic/'registry-repeated.mm',build/'registry-repeated.mm')
    shutil.copyfile(HERE.parents[1]/'tools/video_registry_observer.h',build/'video_registry_observer.h')
    need(sha(build/'video_registry_observer.h')==f['source_hashes']['video_registry_observer.h'],'client header differs')
    dep=newbase/'libDependency.dylib';meta=newbase/'libMetadataRepeat.dylib';host=build/'application';obj=build/'registry-repeated.o'
    common=['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-Wall','-Wextra','-Werror','-Wno-deprecated-declarations']
    frameworks=['-framework','Foundation','-framework','CoreMedia','-framework','VideoToolbox','-framework','CoreVideo','-framework','Metal','-framework','IOKit']
    cmds=[]
    cmds.append(command('dependency',common+['-DKPDEP_RECORD=1','-DKPDEP_ENABLE=1','-dynamiclib',build/'dependency_repeat.mm',*frameworks,'-install_name',dep,'-o',dep],out))
    cmds.append(command('metadata',common+['-fno-omit-frame-pointer','-Wno-frame-address','-DKPMETA_CAPACITY=512','-dynamiclib',build/'metadata_repeat.mm','-framework','Foundation','-framework','CoreFoundation','-install_name',meta,'-o',meta],out))
    for name,binary in [('dependency',dep),('metadata',meta)]:
        cmds.append(command('sign-'+name,['codesign','--force','--sign','-',binary],out))
        cmds.append(command('verify-'+name,['codesign','--verify','--strict',binary],out))
    dp=newbase/'assets/dependency-config.json';cfg=json.loads(dp.read_text());cfg['libraries']['both']=sha(dep);dp.write_text(json.dumps(cfg,indent=2)+'\n')
    rp=newbase/'assets/registry-config.json';cfg=json.loads(rp.read_text());cfg['metadata_library_SHA256']=sha(meta);rp.write_text(json.dumps(cfg,indent=2)+'\n')
    newf=dict(old['frozen'])
    for name in ('libDependency.dylib','libMetadataRepeat.dylib','assets/dependency-config.json','assets/registry-config.json'):
        newf[name]=sha(newbase/name)
    newbase_rec={**old,'frozen':newf,'repeat_observers':True,'original_base_inputs_sha256':sha(base/'inputs.json')}
    (newbase/'inputs.json').write_text(json.dumps(newbase_rec,indent=2,sort_keys=True)+'\n')
    cmds.append(command('compile-host',common+['-fblocks','-DKPREG_CALIBRATION=0','-Dmain=KPRegistryQualifiedMain','-c',build/'registry-repeated.mm','-o',obj],out))
    link=next(x['argv'] for x in json.loads((factory/'commands.json').read_text()) if x['label']=='application')
    oldobj=next(x for x in f['reused_objects_and_libraries_SHA256'] if Path(x).name=='qualified-host-renamed.o')
    olddep=next(x for x in f['reused_objects_and_libraries_SHA256'] if Path(x).name=='libVideoDependency-both.dylib')
    oldmeta=next(x for x in f['reused_objects_and_libraries_SHA256'] if Path(x).name=='libVideoRegistryMetadata.dylib')
    need(all(link.count(x)==1 for x in (oldobj,olddep,oldmeta)) and link[-2:]==['-o',str(factory/'application')],'link plan differs')
    replacements={oldobj:str(obj),olddep:str(dep),oldmeta:str(meta)}
    cmds.append(command('link',[replacements.get(x,x) for x in link[:-2]]+['-o',host],out))
    shutil.copyfile(witness/'entitlements.plist',build/'entitlements.plist')
    cmds.append(command('sign-host',['codesign','--force','--sign','-','--entitlements',build/'entitlements.plist',host],out))
    cmds.append(command('verify-host',['codesign','--verify','--strict',host],out))
    for name in ('marker.S','gva_marker.cpp','lldb_witness.py','lldb_guard.py','marker.dylib'):
        shutil.copyfile(witness/name,build/name)
    frozen={n:sha(build/n) for n in w['frozen']}
    rec={**w,'frozen':frozen,'base_inputs_sha256':sha(newbase/'inputs.json'),'repeat_integrated':True,
         'original_base_inputs_sha256':sha(base/'inputs.json'),'diagnostic_build_sha256':sha(diagnostic/'build.json'),
         'variant_source_sha256':sha(build/'registry-repeated.mm'),'sources_sha256':{n:sha(build/n) for n in SOURCES},
         'dependency_sha256':sha(dep),'metadata_sha256':sha(meta),'builder_sha256':sha(Path(__file__)),
         'GPU_execution':False,'vendor_execution':False}
    (out/'commands.json').write_text(json.dumps(cmds,indent=2)+'\n')
    (build/'build.json').write_text(json.dumps(rec,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':'PREPARED_REPEAT_INTEGRATED','host_sha256':sha(host),'GPU_execution':False}))


if __name__=='__main__':main()
