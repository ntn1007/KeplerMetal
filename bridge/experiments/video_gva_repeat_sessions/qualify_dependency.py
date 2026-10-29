#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise repeated dependency observation in CPU-only controlled processes."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
NAMES=('repeat_gate.h','dependency_repeat.mm','dependency_repeat_test.mm','dependency_inspect_test.mm','video_dependency.h')


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(label,argv,out):
    r=subprocess.run(list(map(str,argv)),capture_output=True,text=True,timeout=90)
    (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr)
    if r.returncode:raise ValueError(label+' failed; inspect retained output')
    return r.stdout.strip()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',required=True,type=Path);p.add_argument('--out',required=True,type=Path);a=p.parse_args()
    base=a.base.resolve();out=a.out.resolve()
    if out.exists() or not out.parent.is_dir():raise ValueError('fresh output required')
    pins=json.loads((base/'inputs.json').read_text())
    for n in ('assets/dependency-config.json','assets/dependency-profile.json','assets/dependency-choice.json'):
        if sha(base/n)!=pins['frozen'][n]:raise ValueError('base input differs')
    out.mkdir()
    for n in NAMES:shutil.copyfile(HERE/n,out/n)
    assets=out/'assets';assets.mkdir()
    for n in ('dependency-config.json','dependency-profile.json','dependency-choice.json'):shutil.copyfile(base/'assets'/n,assets/n)
    lib=out/'libDependencyRepeat.dylib';test=out/'dependency-test';inspect=out/'inspect-test'
    common=['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-Wall','-Wextra','-Werror','-Wno-deprecated-declarations']
    frameworks=['-framework','Foundation','-framework','CoreMedia','-framework','VideoToolbox','-framework','CoreVideo','-framework','Metal','-framework','IOKit']
    run('build-library',common+['-DKPDEP_RECORD=1','-DKPDEP_ENABLE=1','-DKPDEP_TEST=1','-dynamiclib',out/'dependency_repeat.mm',*frameworks,'-install_name',lib,'-o',lib],out)
    run('sign-library',['codesign','--force','--sign','-',lib],out)
    cfg=json.loads((assets/'dependency-config.json').read_text());cfg['libraries']['both']=sha(lib)
    (assets/'dependency-config.json').write_text(json.dumps(cfg,indent=2)+'\n')
    for label,source,binary in [('test','dependency_repeat_test.mm',test),('inspect','dependency_inspect_test.mm',inspect)]:
        run('build-'+label,common+[out/source,lib,*frameworks,'-o',binary],out)
        run('sign-'+label,['codesign','--force','--sign','-',binary],out)
    for label,binary in [('library',lib),('test',test),('inspect',inspect)]:
        run('verify-'+label,['codesign','--verify','--strict',binary],out)
    for i in range(2):
        if run('test-'+str(i),[test],out)!='PASS three independent dependency generations and concurrent refusal':raise ValueError('dependency control differs')
        if run('inspect-'+str(i),[inspect,assets],out)!='PASS three pinned-profile inspection scopes and six public IOKit controls':raise ValueError('profile control differs')
    result={'status':'PASS_REPEAT_DEPENDENCY_CPU_SCOPES','observer_processes':2,'observer_generations':6,
            'pinned_profile_processes':2,'pinned_profile_generations':6,'profile_iokit_positive_negative_controls':12,
            'base_inputs_sha256':sha(base/'inputs.json'),'profile_sha256':sha(assets/'dependency-profile.json'),
            'config_sha256':sha(assets/'dependency-config.json'),'sources_sha256':{n:sha(out/n) for n in NAMES},
            'qualifier_sha256':sha(Path(__file__)),'library_sha256':sha(lib),'observer_host_sha256':sha(test),'inspect_host_sha256':sha(inspect),
            'logs_sha256':{n:sha(out/(n+'.stdout')) for n in ('test-0','test-1','inspect-0','inspect-1')},
            'test_seam_enabled':True,'video_session_creation_tested':False,'video_host_integration':False,
            'gpu_execution':False,'hardware_video_execution_proved':False,'system_modified':False}
    (out/'qualification.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':result['status'],'observer_generations':6,'profile_generations':6,'GPU_execution':False}))


if __name__=='__main__':main()
