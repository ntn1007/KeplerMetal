#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare a manually qualified exact conditional-CAS SDK profile; no GPU work."""
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
from metallib_air import extract
from recognize_native_cas import air_contract,verify_decoder


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def need(value,message):
    if not value:raise ValueError(message)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('lab','capture','analysis','proof','reproduction-proof','out'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();lab=a.lab.resolve();capture=a.capture.resolve();analysis=a.analysis.resolve();out=a.out.resolve()
    for item in (capture,analysis,a.proof.resolve(),a.reproduction_proof.resolve(),out):item.relative_to(lab/'results')
    need(not out.exists(),'fresh output required')
    need(sha(a.proof)=='2822b5b2a4bb17ed51ebfd037e5f2039e075334a1c914e149337605f467c7fa3' and
         sha(a.reproduction_proof)=='79cf6f35c3dd814d96791f6730225f0e0bff6957c33e93c701fa845ec8aab650',
         'retained GPU audits differ')
    for path in (a.proof,a.reproduction_proof):
        proof=json.loads(path.read_text());repaired=[x for x in proof['receipts'] if x['mode']=='repaired']
        need(proof['status']=='PASS' and len(repaired)==2 and
             sum(x['active_CAS_operations'] for x in repaired)==56904 and
             all(not any(x['totals'].values()) for x in repaired),'retained GPU qualification differs')
    state=json.loads((analysis/'analysis.json').read_text());typed=(analysis/'typed-air.json').read_bytes()
    library=(capture/'input.metallib').read_bytes();original=(capture/'native.sass').read_bytes()
    metadata=(capture/'native.metadata').read_bytes();listing=(analysis/'native.asm').read_text()
    decoder=lab/'build/envydis-only/envydis/envydis'
    need(state['status']=='PASS' and state['AIR_contract']==air_contract(json.loads(typed),'divergence_case') and
         not state['AIR_contract']['qualified'] and state['flow_refusal']=={'status':'REFUSED','reason':'indirect or unsupported branch'} and
         sha(analysis/'typed-air.json')==state['typed_AIR_SHA256'] and sha(capture/'input.metallib')==state['library_SHA256'] and
         sha(capture/'native.sass')==state['native_SHA256'] and sha(capture/'native.metadata')==state['native_metadata_SHA256'] and
         verify_decoder(original,listing,decoder),'retained conditional diagnosis differs')
    result=subprocess.run([sys.executable,str(EXPERIMENT/'prepare_repair.py'),'--lab',str(lab),
                           '--capture',str(capture),'--out',str(out)],capture_output=True,timeout=150)
    need(result.returncode==0,'low-level preparation failed: '+result.stderr.decode(errors='replace')[-2000:])
    module=extract(library,'divergence_case');module.pop('wrapped_AIR')
    air=dict(state['AIR_contract'],expected_output_component=0,
             component_evidence='manual source and bounded GPU qualification; not an AIR-contract verdict')
    sass={'qualified':False,'reason':'indirect or unsupported branch','expected_output_component':0,
          'old_register':0,'expected_register':4,'redirect_offset':0x428,'return_offset':0x430}
    cert={'schema':1,'candidate':True,'function':'divergence_case','intent':'post_CAS_expected',
          'repair_profile':'gk104-conditional-pinned-v1','qualification':'manual-exact-profile-gpu-tested',
          'SASS_only_repair_forbidden':True,'AIR':air,'SASS':sass,'embedded_AIR':module,
          'library_SHA256':sha(out/'shader.metallib')}
    for name,data in [('original_code',original),('repaired_code',(out/'repaired.sass').read_bytes()),('native_metadata',metadata)]:
        cert[name+'_base64']=base64.b64encode(data).decode();cert[name+'_SHA256']=hashlib.sha256(data).hexdigest()
    (out/'certificate.json').write_text(json.dumps(cert,indent=2)+'\n')
    source=(out/'repair_host.mm').read_text();needle='KPInternalCASCreatePreservingNativeCASPipeline'
    need(source.count(needle)==2,'laboratory host shape differs')
    (out/'sdk_host.mm').write_text(source.replace(needle,'KPCertifiedConditionalCASPipeline'))
    shutil.copyfile(EXPERIMENT/'sdk_wrapper.mm',out/'sdk_wrapper.mm')
    cmd=['clang++','-arch','x86_64','-O2','-std=c++17','-fno-objc-arc','-I',str(out/'src'),
         str(out/'sdk_host.mm'),str(out/'import.mm'),str(out/'sdk_wrapper.mm'),
         '-framework','Metal','-framework','Foundation','-o',str(out/'host-sdk')]
    built=subprocess.run(cmd,capture_output=True,timeout=120);(out/'sdk-build.stderr').write_bytes(built.stderr)
    need(built.returncode==0,'SDK host build failed')
    sdk={'host_SHA256':sha(out/'host-sdk'),'host_source_SHA256':sha(out/'sdk_host.mm'),
         'wrapper_SHA256':sha(out/'sdk_wrapper.mm'),'adapter_SHA256':sha(out/'src/KeplerNativeCASAdapter.inc'),
         'certificate_SHA256':sha(out/'certificate.json'),'qualification_audit_SHA256':sha(a.proof),
         'reproduction_audit_SHA256':sha(a.reproduction_proof),'recognizer_status':'refused; exact profile only',
         'GPU_dispatch':False}
    (out/'sdk-build.json').write_text(json.dumps(sdk,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':'PREPARED','GPU_dispatch':False,'host_SHA256':sdk['host_SHA256']}))


if __name__=='__main__':main()
