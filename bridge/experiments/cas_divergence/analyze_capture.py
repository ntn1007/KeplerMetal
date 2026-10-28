#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Inspect a captured conditional-CAS program offline; never authorize dispatch."""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

BRIDGE=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(BRIDGE/'tools'))
from metallib_air import extract
from recognize_native_cas import air_contract,verify_decoder
from trace_native_cas_flow import instructions_from_listing,trace_region


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def need(value,message):
    if not value:raise ValueError(message)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('lab','capture','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();lab=a.lab.resolve();capture=a.capture.resolve();out=a.out.resolve()
    capture.relative_to(lab/'results');out.relative_to(lab/'results')
    need(not out.exists() and out.parent.is_dir(),'fresh output required')
    manifest=json.loads((capture/'manifest.json').read_text())
    need(manifest['GPU_reservation']['state']=='terminal' and not manifest['SIGKILL_requested'] and
         not manifest['authoritative_ps_status'] and manifest['exit_code']==0 and
         sha(capture/'input.metallib')==manifest['library_SHA256'],'capture receipt differs')
    program=(capture/'native.sass').read_bytes();library=(capture/'input.metallib').read_bytes()
    module=extract(library,'divergence_case');module_bytes=module.pop('wrapped_AIR')
    decoder=lab/'build/envydis-only/envydis/envydis'
    need(sha(decoder)=='1c8730a9a4861f374c58407bff31d7ccb47a57eb23f9f82c6b3ea3deb079be0f','decoder pin differs')
    out.mkdir();(out/'embedded.air').write_bytes(module_bytes)
    vendor=lab/'vendor/OpenNVDA-da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5/drivers/NVMTLDriver/air'
    command=['clang','-O2','-I'+str(vendor),str(BRIDGE/'tools/metallib_air_dump.c'),
             str(lab/'build/air-bitstream.o'),str(lab/'build/air-airir.o'),'-o',str(out/'reader')]
    build=subprocess.run(command,capture_output=True,timeout=60)
    (out/'build.stderr').write_bytes(build.stderr);need(build.returncode==0,'AIR reader build failed')
    read=subprocess.run([str(out/'reader'),str(out/'embedded.air'),'divergence_case'],capture_output=True,timeout=30)
    (out/'read.stderr').write_bytes(read.stderr);need(read.returncode==0,'AIR reader failed')
    typed=json.loads(read.stdout);(out/'typed-air.json').write_bytes(read.stdout)
    air=air_contract(typed,'divergence_case')
    dis=subprocess.run([str(decoder),'-m','gf100','-V','gk104','-i','-n',str(capture/'native.sass')],
                       capture_output=True,timeout=30)
    need(dis.returncode==0,'native decode failed');listing=dis.stdout.decode()
    need(verify_decoder(program,listing,decoder),'native decoder replay failed');(out/'native.asm').write_text(listing)
    ins=instructions_from_listing(program,listing)
    indirect=[{'offset':offset,'operation':op} for offset,op in ins if re.search(r'\bbra \$r\d+',op)]
    locks=[offset for offset,op in ins if op.startswith('ld lock ')]
    need(len(indirect)==1 and indirect[0]['offset']==0x290 and 0x3a8 in locks, 'unexpected native capture profile')
    indexes={off:i for i,(off,_) in enumerate(ins)}
    need(ins[indexes[0x3d8]][1]=='join nop' and ins[indexes[0x420]][1]=='set $p0 0x1 eq u32 $r4 $r0',
         'unexpected comparison shape')
    try:trace_region(ins,indexes[0x3e0],indexes[0x420],0,4)
    except ValueError as error:flow={'status':'REFUSED','reason':str(error)}
    else:raise ValueError('indirect branch unexpectedly accepted')
    need(flow['reason']=='indirect or unsupported branch','unexpected flow refusal')
    result={'status':'PASS','library_SHA256':sha(capture/'input.metallib'),
            'native_SHA256':sha(capture/'native.sass'),'native_metadata_SHA256':sha(capture/'native.metadata'),
            'typed_AIR_SHA256':sha(out/'typed-air.json'),'decoder_SHA256':sha(decoder),
            'decoder_reproduced_listing':True,'AIR_contract':air,'indirect_branch_offsets':[x['offset'] for x in indirect],
            'lock_offsets':locks,'conditional_lock_offset':0x3a8,'flow_refusal':flow,
            'compiler_capture_GPU_dispatch':False,'resident_instruction_readback':False,
            'certificate_authorized':False,'GPU_dispatch_by_offline_analysis':False}
    (out/'analysis.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
