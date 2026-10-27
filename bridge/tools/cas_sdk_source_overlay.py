#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare a source-only CAS SDK workspace using an existing shared lab lease."""
import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
from public_large_scratch import ROOT, sha
from video_metal_resource_observer import check_profile


def require(value, message):
    if not value: raise ValueError(message)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--lab-root',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    lab=a.lab_root.resolve();out=a.out.resolve();out.relative_to(lab/'results')
    require(not out.exists() and out.parent.is_dir() and (lab/'results').is_dir(),'Fresh output under existing lab results required')
    profile=check_profile();fixture_root=lab/'results/native-cas-variants-captured';rows=json.loads((fixture_root/'fixtures.json').read_text())
    require(len(rows)==4 and {x['name'] for x in rows}=={'slot1','live_noise','permuted','original_compare_control'},'Fixture inventory differs')
    sources={}
    for row in rows:
        data=(fixture_root/row['name']/'test.metal').read_bytes();digest=hashlib.sha256(data).hexdigest()
        require(digest==row['hashes']['test.metal'],'Fixture source differs');sources[row['name']]=data
    required=['build/compiler_output_trace','build/air-bitstream.o','build/air-airir.o','build/envydis-only/envydis/envydis',
              'results/native-cas-repaired/envyas','results/native-cas-sdk-source-provenance.json',
              'tools/run_signed_probe.py','tools/lab_gpu_reservation.py','tools/lab_phase_timing.py']
    for name in required:require((lab/name).is_file(),'Lab dependency missing: '+name)
    for name in ('run_signed_probe.py','lab_gpu_reservation.py','lab_phase_timing.py'):
        require(sha(lab/'tools'/name)==sha(ROOT/'tools'/name),'Shared launcher differs: '+name)
    require(sha(lab/'build/envydis-only/envydis/envydis')=='1c8730a9a4861f374c58407bff31d7ccb47a57eb23f9f82c6b3ea3deb079be0f','Decoder pin differs')
    require((lab/'vendor/OpenNVDA-da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5/drivers/NVMTLDriver/air').is_dir(),'AIR source dependency absent')
    out.mkdir();(out/'tools').mkdir();(out/'results').mkdir();shutil.copytree(ROOT/'src',out/'src')
    (out/'sdk-cas/examples').mkdir(parents=True)
    for name in ('client.mm','build_example.py'):shutil.copyfile(ROOT/'sdk-cas/examples'/name,out/'sdk-cas/examples'/name)
    names=('prepare_native_cas_sdk.py','build_native_cas_sdk_module.py','plan_native_metallib_repair.py','recognize_native_cas.py','metallib_air.py','metallib_air_dump.c','public_large_scratch.py')
    for name in names:shutil.copyfile(ROOT/'tools'/name,out/'tools'/name)
    for name in ('run_signed_probe.py','lab_gpu_reservation.py','lab_phase_timing.py'):os.symlink(lab/'tools'/name,out/'tools'/name)
    for name in ('vendor','build'):os.symlink(lab/name,out/name)
    os.symlink(lab/'results/native-cas-repaired',out/'results/native-cas-repaired')
    shutil.copyfile(lab/'results/native-cas-sdk-source-provenance.json',out/'results/native-cas-sdk-source-provenance.json')
    dest=out/'results/native-cas-variants-captured';dest.mkdir();shutil.copyfile(fixture_root/'fixtures.json',dest/'fixtures.json')
    for name,data in sources.items():(dest/name).mkdir();(dest/name/'test.metal').write_bytes(data)
    frozen={str(x.relative_to(out)):sha(x) for folder in ('src','tools','sdk-cas','results/native-cas-variants-captured') for x in (out/folder).rglob('*') if x.is_file() and not x.is_symlink()}
    evidence={'source_SHA256':frozen,'lab_dependencies_SHA256':{name:sha(lab/name) for name in required},'profile':profile,'GPU_dispatch':False,'scope':'Isolated source overlay using the existing lab reservation; vendor dependencies stay local'}
    (out/'inputs.json').write_text(json.dumps(evidence,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':'PASS','source_files':len(frozen),'fixture_sources':len(sources),'GPU_dispatch':False}))
if __name__=='__main__':main()
