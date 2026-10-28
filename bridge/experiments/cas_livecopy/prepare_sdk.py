#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build a pinned CAS SDK client and certificate; does not dispatch GPU work."""
import argparse
import base64
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

EXPERIMENT=Path(__file__).resolve().parent
BRIDGE=EXPERIMENT.parents[1]
sys.path.insert(0,str(BRIDGE/'tools'))
from recognize_native_cas import air_contract,verify_decoder


def sha(data):return hashlib.sha256(data).hexdigest()
def need(value,message):
    if not value:raise ValueError(message)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lab',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();lab=args.lab.resolve();out=args.out.resolve()
    out.relative_to(lab/'results');need(not out.exists(),'fresh output required')
    result=subprocess.run([sys.executable,str(EXPERIMENT/'prepare.py'),'--lab',str(lab),'--out',str(out)],
                          capture_output=True,timeout=150)
    need(result.returncode==0,'base preparation failed: '+result.stderr.decode(errors='replace')[-2000:])
    fixture=lab/'results/cas-dynamic-overlay-20261028-01/results/dynamic-checked-diagnosis'
    diagnosis=json.loads((fixture/'diagnosis.json').read_text())
    module=json.loads((fixture/'typed-air.json').read_text())
    code=(out/'original.sass').read_bytes();replacement=(out/'repaired.sass').read_bytes()
    library=(out/'test.metallib').read_bytes();metadata=(fixture/'native.metadata').read_bytes()
    need(sha(metadata)=='b688a341c68920bb8e8c383f5a2a87d37ac5a1c93a962a531ff8f4a289ecbf12','metadata differs')
    need(diagnosis['candidate'] is False and diagnosis['AIR']==air_contract(module,'test') and
         diagnosis['AIR']['qualified'] and diagnosis['decoder_reproduced_listing'], 'AIR diagnosis differs')
    need(verify_decoder(code,(fixture/'native.asm').read_text(),lab/'build/envydis-only/envydis/envydis'),
         'native decoder replay differs')
    need(sha(library)==diagnosis['input_library_SHA256'] and
         sha(code)==diagnosis['artifact_SHA256']['native.sass'], 'diagnosis snapshot differs')
    cert={'schema':1,'candidate':True,'function':'test','intent':'post_CAS_expected',
          'repair_profile':'gk104-livecopy-pinned-v1','SASS_only_repair_forbidden':True,
          'AIR':diagnosis['AIR'],'embedded_AIR':diagnosis['embedded_AIR'],
          'SASS':{'qualified':True,'expected_output_component':0,'old_register':5,'expected_register':0,
                  'redirect_offset':0x530,'return_offset':0x538,
                  'qualification':'manually GPU-qualified exact byte profile; general SASS recognizer refused'},
          'library_SHA256':sha(library)}
    for name,data in [('original_code',code),('repaired_code',replacement),('native_metadata',metadata)]:
        cert[name+'_base64']=base64.b64encode(data).decode();cert[name+'_SHA256']=sha(data)
    (out/'certificate.json').write_text(json.dumps(cert,indent=2)+'\n')
    shutil.copyfile(EXPERIMENT/'sdk_wrapper.mm',out/'sdk_wrapper.mm')
    cmd=['clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc',
         '-DPINNED_NATIVE_CAS_IMPORT','-DCOMPILED_METALLIB_CAS_IMPORT',
         '-I',str(out/'src'),str(out/'probe.mm'),str(out/'import.mm'),str(out/'sdk_wrapper.mm'),
         '-framework','Metal','-framework','Foundation','-o',str(out/'probe-sdk')]
    build=subprocess.run(cmd,capture_output=True,timeout=120)
    (out/'sdk-build.stderr').write_bytes(build.stderr);need(build.returncode==0,'SDK client build failed')
    shutil.copyfile(out/'probe',out/'probe-lowlevel');(out/'probe-sdk').replace(out/'probe')
    manifest={'certificate_SHA256':sha((out/'certificate.json').read_bytes()),
              'adapter_SHA256':sha((out/'src/KeplerNativeCASAdapter.inc').read_bytes()),
              'wrapper_SHA256':sha((out/'sdk_wrapper.mm').read_bytes()),
              'probe_SHA256':sha((out/'probe').read_bytes()),
              'previous_probe_SHA256':sha((out/'probe-lowlevel').read_bytes()),
              'candidate_origin':'pinned GPU-qualified profile; not general recognizer',
              'GPU_dispatch':False}
    (out/'sdk-build.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'status':'PREPARED','GPU_dispatch':False,'probe_SHA256':manifest['probe_SHA256']}))


if __name__=='__main__':main()
