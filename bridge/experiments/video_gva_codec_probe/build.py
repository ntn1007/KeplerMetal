#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build a process-local, narrowly pinned synthetic property observer."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok,msg):
    if not ok:raise ValueError(msg)
def run(label,argv,out):
    r=subprocess.run(list(map(str,argv)),capture_output=True,text=True,timeout=90)
    (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr)
    need(r.returncode==0,label+' failed; inspect retained output');return r.stdout


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('lab','base','out'):p.add_argument('--'+n,required=True,type=Path)
    a=p.parse_args();lab,base,out=(getattr(a,n).resolve() for n in ('lab','base','out'))
    for x in (base,out):x.relative_to(lab/'results')
    need(not out.exists() and out.parent.is_dir(),'fresh output required')
    b=json.loads((base/'inputs.json').read_text())
    for n,h in b['frozen'].items():need(sha(base/n)==h,'base differs: '+n)
    need(b['new_registry_ID']==4294968416,'registry profile differs')
    source=base/'observer.mm';need(sha(source)==b['frozen']['observer.mm'],'observer source differs')
    original=source.read_text();anchor='int type=0;uint32_t numeric=0;bool numericOK=false,stringOK=false;'
    inject='''const char *probe=getenv("KP_GVA_CODEC_PROBE");bool originalNull=!value;
    bool keyMatch=keyOK&&CFEqual(key,CFSTR("IOGVACodec"));
    bool classMatch=classOK&&!strcmp(className,"nvAccelerator");
    bool idMatch=idOK&&registry==KP_CODEC_REGISTRY_ID;
    const char *effective=probe;
    if(probe&&!strcmp(probe,"wrong-key")){keyMatch=false;effective="synthetic";}
    if(probe&&!strcmp(probe,"wrong-id")){idMatch=false;effective="synthetic";}
    bool changed=KPCodecProbeAllowed(effective,profile,offset,keyMatch,classMatch,idMatch,originalNull,options);
    if(changed)value=CFRetain(CFSTR("KeplerMetalProbe"));
    if(watched&&offset==150812){char msg[180];int n=snprintf(msg,sizeof(msg),"KM_CODEC_PROBE original_null=%d injected=%d profile=%d\\n",originalNull?1:0,changed?1:0,profile?1:0);if(n>0&&n<(int)sizeof(msg))write(STDERR_FILENO,msg,(size_t)n);}
    '''+anchor
    need(original.count(anchor)==1,'property observer shape differs')
    out.mkdir();newbase=out/'base';shutil.copytree(base,newbase)
    (newbase/'observer.mm').write_text('#include "predicate.h"\n'+original.replace(anchor,inject))
    shutil.copyfile(HERE/'predicate.h',newbase/'predicate.h')
    for n in ('predicate_test.cpp','cfstring_test.cpp'):shutil.copyfile(HERE/n,out/n)
    common=['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-Wall','-Wextra','-Werror']
    run('predicate-build',common+[out/'predicate_test.cpp','-I',newbase,'-o',out/'predicate-test'],out)
    run('cfstring-build',common+[out/'cfstring_test.cpp','-I',newbase,'-framework','CoreFoundation','-o',out/'cfstring-test'],out)
    need(run('predicate-run',[out/'predicate-test'],out).strip()=='PASS one synthetic property predicate and nine refusals','predicate control differs')
    need(run('cfstring-run',[out/'cfstring-test'],out).strip()=='PASS CFString type ownership conversion and original preservation','CFString control differs')
    observer=newbase/'libObserver.dylib'
    run('observer-build',['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-Wno-deprecated-declarations',
        '-DKP_CODEC_REGISTRY_ID=4294968416ull','-dynamiclib',newbase/'observer.mm','-framework','Foundation','-framework','Metal',
        '-framework','CoreFoundation','-framework','IOKit','-o',observer],out)
    run('observer-sign',['codesign','--force','--sign','-',observer],out);run('observer-verify',['codesign','--verify','--strict',observer],out)
    frozen=dict(b['frozen']);
    for n in ('observer.mm','predicate.h','libObserver.dylib'):frozen[n]=sha(newbase/n)
    record={**b,'frozen':frozen,'codec_probe_variant':True,'original_inputs_sha256':sha(base/'inputs.json'),
            'predicate_sha256':sha(newbase/'predicate.h'),'builder_sha256':sha(Path(__file__)),'GPU_execution':False}
    (newbase/'inputs.json').write_text(json.dumps(record,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':'PREPARED_SYNTHETIC_PROPERTY_OBSERVER','GPU_execution':False,'value_is_NVIDIA_proved':False}))


if __name__=='__main__':main()
