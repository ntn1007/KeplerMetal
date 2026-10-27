#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze a locally regenerated CAS SDK and qualify its explicit client on GTX."""
import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from public_large_scratch import ROOT, preflight, read, sha, write
from video_metal_resource_observer import check_profile

SUPPORT = ('cas_sdk_qualification.py','verify_native_cas_sdk.py','verify_local_memory.py',
           'public_large_scratch.py','video_metal_resource_observer.py')

def require(value, message):
    if not value: raise ValueError(message)

def build(a):
    source=a.sdk.resolve(); out=a.out.resolve(); preflight(out); profile=check_profile()
    manifest=read(source/'BUILD_MANIFEST.json'); assets=read(source/'assets/client-manifest.json')
    require(manifest.get('decoder_evidence_required') is True, 'SDK must require decoder evidence')
    require(assets['driver_SHA256']==profile['system_files_SHA256']['/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver'], 'SDK driver profile differs')
    require(sha(source/'lib/libKeplerNativeCAS.a')==manifest['static_archive_SHA256'], 'SDK archive differs')
    for name,digest in manifest['source_SHA256'].items():
        require(sha(source/name)==digest==sha(ROOT/name), 'SDK source differs: '+name)
    for name,digest in manifest['example_SHA256'].items():
        require(sha(source/name)==digest==sha(ROOT/'sdk-cas'/name), 'SDK example differs: '+name)
    for name,digest in manifest['assets_SHA256'].items():require(sha(source/'assets'/name)==digest, 'SDK asset differs: '+name)
    require(sha(source/'assets'/assets['library'])==assets['library_SHA256'], 'SDK library differs')
    for row in assets['profiles']:
        cert=source/'assets'/row['certificate'];require(sha(cert)==row['certificate_SHA256'], 'Certificate differs')
        if row['candidate']:require(read(cert).get('decoder_reproduced_listing') is True, 'Decoder evidence absent')
    require(sum(bool(x['candidate']) for x in assets['profiles'])==4 and len(assets['profiles'])==5, 'Certificate profile set differs')
    out.mkdir();shutil.copytree(source,out/'sdk');(out/'support').mkdir();(out/'runtime').mkdir()
    for name in SUPPORT:shutil.copyfile(ROOT/'tools'/name,out/'support'/name)
    shutil.copyfile(ROOT/'sdk-combined/runtime/run_sdk_host.py',out/'runtime/run_sdk_host.py')
    shutil.copyfile(ROOT/'tools/lab_gpu_reservation.py',out/'runtime/lab_gpu_reservation.py')
    argv=[sys.executable,str(out/'sdk/examples/build_example.py'),'--out',str(out/'client')]
    r=subprocess.run(argv,capture_output=True,text=True,timeout=90)
    (out/'build.stdout').write_text(r.stdout);(out/'build.stderr').write_text(r.stderr)
    require(r.returncode==0, 'SDK client build failed; inspect '+str(out/'build.stderr'))
    ci=read(out/'client/inputs.json');require(ci['module_static_library_SHA256']==manifest['static_archive_SHA256'] and ci['core_source_compilations']==0, 'Client archive differs')
    frozen={str(p.relative_to(out)):sha(p) for folder in ('sdk','client','support','runtime') for p in (out/folder).rglob('*') if p.is_file()}
    write(out/'inputs.json',{'frozen':frozen,'profile':profile,'user_UID':os.getuid(),'SDK_archive_SHA256':manifest['static_archive_SHA256'],
          'executable_SHA256':sha(out/'client/cas_example'),'SDK_manifest_SHA256':sha(out/'sdk/BUILD_MANIFEST.json'),'GPU_execution':False})
    print(json.dumps({'status':'BUILD_PASS','GPU_execution':False,'executable_SHA256':sha(out/'client/cas_example')}))

def run(a):
    build=a.build.resolve();out=a.out.resolve();i=read(build/'inputs.json')
    require(not out.exists() and out.parent.is_dir() and (a.reservation_root/'results').is_dir(), 'Fresh output and lab reservation required')
    for path,digest in i['frozen'].items():require(sha(build/path)==digest, 'Frozen input changed: '+path)
    require(check_profile()==i['profile'] and os.getuid()==i['user_UID'], 'Machine profile or user changed')
    require(sha(ROOT/'tools/cas_sdk_qualification.py')==i['frozen']['support/cas_sdk_qualification.py'], 'Coordinator changed')
    out.mkdir();shutil.copytree(build/'sdk/assets',out/'assets');shutil.copytree(build/'support',out/'support');shutil.copytree(build/'runtime',out/'runtime')
    shutil.copyfile(build/'client/cas_example',out/'application');(out/'application').chmod(0o755);(out/'outputs').mkdir()
    write(out/'inputs.json',dict(i,mode=a.mode,build_inputs_SHA256=sha(build/'inputs.json')))
    sys.path.insert(0,str(out/'runtime'));from run_sdk_host import run_host
    result=run_host(out/'application',out/'execution',[str(out/'assets'),str(out/'assets/client-manifest.json'),str(out/'outputs'),a.mode],a.reservation_root.resolve())
    require(check_profile()==i['profile'], 'Profile changed after host; retain evidence')
    for path,digest in i['frozen'].items():
        if path.startswith('sdk/assets/'):
            require(sha(out/'assets'/path[len('sdk/assets/'):])==digest, 'Copied asset changed: '+path)
    require(result['GPU_reservation']['state']=='terminal' and not result['GPU_reservation']['known_signed_processes_live'], 'Host reservation not terminal')
    require(sha(out/'application')==i['executable_SHA256']==result['original_binary_sha256'] and sha(out/'execution/application')==result['signed_binary_sha256'], 'Executable identity differs')
    write(out/'results.json',read(out/'execution/execution.stdout'))
    code='import json,sys;from pathlib import Path;sys.path.insert(0,sys.argv[1]);from verify_native_cas_sdk import verify;r=verify(Path(sys.argv[2]));print(json.dumps(r,sort_keys=True))'
    v=subprocess.run([sys.executable,'-I','-c',code,str(out/'support'),str(out)],capture_output=True,text=True,timeout=120)
    (out/'verification.stdout').write_text(v.stdout);(out/'verification.stderr').write_text(v.stderr)
    require(v.returncode==0,'Independent CPU verifier failed; inspect '+str(out/'verification.stderr'))
    data=json.loads(v.stdout);write(out/'independent-verification.json',data)
    print(json.dumps({k:v for k,v in data.items() if k!='records'},sort_keys=True))

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(required=True)
    b=s.add_parser('build');b.add_argument('--sdk',type=Path,required=True);b.add_argument('--out',type=Path,required=True);b.set_defaults(fn=build)
    r=s.add_parser('run');r.add_argument('--build',type=Path,required=True);r.add_argument('--out',type=Path,required=True);r.add_argument('--reservation-root',type=Path,required=True);r.add_argument('--mode',choices=['negative','prepare','native','execute'],required=True);r.set_defaults(fn=run)
    a=p.parse_args();a.fn(a)
if __name__=='__main__':main()
