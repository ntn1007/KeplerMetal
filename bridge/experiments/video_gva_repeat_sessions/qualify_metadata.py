#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build and exercise the experimental repeat gate and metadata observer on CPU."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
NAMES=('repeat_gate.h','repeat_gate_test.cpp','metadata_repeat.mm','metadata_repeat_test.mm','video_registry_metadata.h')


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(label, argv, out):
    r=subprocess.run(list(map(str,argv)),capture_output=True,text=True,timeout=60)
    (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr)
    if r.returncode:raise ValueError(label+' failed; output retained')
    return r.stdout


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();out=a.out.resolve()
    if out.exists() or not out.parent.is_dir():raise ValueError('fresh output required')
    out.mkdir()
    for name in NAMES:shutil.copyfile(HERE/name,out/name)
    gate=out/'gate-test';lib=out/'libMetadataRepeat.dylib';host=out/'metadata-test'
    common=['xcrun','clang++','-arch','x86_64','-O2','-std=c++17','-Wall','-Wextra','-Werror']
    run('build-gate',common+['-pthread',out/'repeat_gate_test.cpp','-o',gate],out)
    run('build-lib',common+['-fno-objc-arc','-fno-omit-frame-pointer','-Wno-deprecated-declarations',
        '-Wno-frame-address','-dynamiclib',out/'metadata_repeat.mm','-framework','Foundation',
        '-framework','CoreFoundation','-install_name',lib,'-o',lib],out)
    run('sign-lib',['codesign','--force','--sign','-',lib],out)
    run('build-host',common+['-fno-objc-arc',out/'metadata_repeat_test.mm',lib,'-framework','Foundation',
        '-framework','CoreFoundation','-o',host],out)
    for label,binary in [('host',host),('gate',gate)]:run('sign-'+label,['codesign','--force','--sign','-',binary],out)
    for label,binary in [('host',host),('gate',gate),('lib',lib)]:run('verify-'+label,['codesign','--verify','--strict',binary],out)
    for i in range(2):
        if not run('gate-'+str(i),[gate],out).startswith('PASS repeat epochs, contention, drain, timeout and 300 concurrent cycles ('):
            raise ValueError('gate results differ')
        if run('metadata-'+str(i),[host],out).strip()!='PASS three independent metadata generations and concurrent refusal':
            raise ValueError('metadata results differ')
    result={'status':'PASS_CPU_REPEAT_METADATA_PROTOTYPE','gate_cycles':600,'worker_threads_per_process':4,
            'metadata_processes':2,'metadata_generations_per_process':3,'negative_cases':['wrong-owner','concurrent-begin','invalid-sites','stale-ticket','timeout-poison'],
            'qualifier_sha256':sha(Path(__file__)),'sources_sha256':{name:sha(out/name) for name in NAMES},'gate_sha256':sha(gate),'library_sha256':sha(lib),'host_sha256':sha(host),
            'logs_sha256':{label:sha(out/(label+'.stdout')) for label in ('gate-0','gate-1','metadata-0','metadata-1')},
            'integration_in_video_host':False,'gpu_execution':False,'hardware_video_execution_proved':False,'system_modified':False}
    (out/'qualification.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':result['status'],'metadata_generations':6,'gate_cycles':600,'GPU_execution':False}))


if __name__=='__main__':main()
