#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reproduce copied-register flow plus decoded offline adversarial mutations."""
import argparse
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from recognize_native_cas import air_contract, verify_decoder
from trace_native_cas_flow import analyze


def sha(data):return hashlib.sha256(data).hexdigest()
def need(value,message):
    if not value:raise ValueError(message)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('diagnosis','assembler','decoder','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();d=a.diagnosis.resolve();out=a.out.resolve()
    need(not out.exists() and out.parent.is_dir(),'fresh output required')
    original=(d/'native.sass').read_bytes();listing=(d/'native.asm').read_text()
    typed=(d/'typed-air.json').read_bytes();state=json.loads((d/'diagnosis.json').read_text())
    need(sha(original)=='f16bf16da56d5dc060429f6886d2e1d80eafa0a960f48b7d776a3234fb6bcb41',
         'native program differs')
    need(sha(a.assembler.read_bytes())=='1f023d5e1f0a5afc3a04510e264159923dac3182139e03c0a67600b9b1d4428e',
         'assembler differs')
    need(verify_decoder(original,listing,a.decoder),'decoder reproduction differs')
    air=air_contract(json.loads(typed),state['function'])
    need(air==state['AIR'] and air['qualified'] and sha(typed)==state['artifact_SHA256']['typed-air.json'],
         'AIR diagnosis differs')
    baseline=analyze(original,listing,air)
    need(baseline['status']=='HYPOTHESIS_ONLY' and len(baseline['hypotheses'])==1 and
         baseline['hypotheses'][0]['CAS_offset']==0x350 and
         baseline['hypotheses'][0]['saved_register']==5 and
         baseline['hypotheses'][0]['redirect_offset']==0x530, 'unexpected original flow')
    siblings=[]
    for name in ('dynamic-before-diagnosis','dynamic-multi-diagnosis',
                 'dynamic-neighbor-diagnosis','dynamic-noise-diagnosis'):
        sibling=d.parent/name
        code=(sibling/'native.sass').read_bytes();text=(sibling/'native.asm').read_text()
        typed_sibling=(sibling/'typed-air.json').read_bytes()
        state_sibling=json.loads((sibling/'diagnosis.json').read_text())
        sibling_air=air_contract(json.loads(typed_sibling),state_sibling['function'])
        need(sibling_air==state_sibling['AIR'] and sibling_air['qualified'] and
             sha(code)==state_sibling['artifact_SHA256']['native.sass'] and
             sha(typed_sibling)==state_sibling['artifact_SHA256']['typed-air.json'] and
             verify_decoder(code,text,a.decoder), 'sibling provenance differs: '+name)
        verdict=analyze(code,text,sibling_air)
        need(verdict['status']=='REFUSED' and not verdict['hypotheses'] and
             not verdict['certificate_authorized'], 'unexpected sibling hypothesis: '+name)
        siblings.append({'name':name,'native_SHA256':sha(code),'flow_status':verdict['status']})
    variants=[('copy_wrong_source',0x3c8,'mov b32 $r5 $r4','saved register is not a must-alias'),
              ('jump_over_copy',0x3b8,'bra 0x3d0','saved register is not a must-alias'),
              ('destroy_saved_copy',0x3d8,'mov b32 $r5 0x0','saved register is not a must-alias'),
              ('overwrite_expected',0x3d8,'mov b32 $r0 0x0','comparison input overwritten'),
              ('join_inside_region',0x3d8,'join nop','unsupported control flow in tracked slice'),
              ('jump_into_region',0x348,'bra 0x3d8','branch enters tracked slice'),
              ('extra_expected_use',0x538,'mov b32 $r9 $r0','unqualified later use')]
    results=[]
    with tempfile.TemporaryDirectory(prefix='kepler-cas-flow-audit-') as temporary:
        tmp=Path(temporary)
        for name,offset,operation,reason in variants:
            source=tmp/(name+'.easm');assembled=tmp/(name+'.bin');codefile=tmp/(name+'.sass')
            source.write_text('.section #code 0;\n.skip %#x;\nlong %s;\n'%(offset,operation))
            result=subprocess.run([str(a.assembler),'-m','gf100','-V','gk104','-i','-o',str(assembled),str(source)],
                                  capture_output=True,timeout=20)
            need(result.returncode==0,'assembly failed: '+name)
            raw=assembled.read_bytes();need(len(raw)>=offset+8,'assembled word missing')
            code=bytearray(original);code[offset:offset+8]=raw[offset:offset+8];code=bytes(code)
            need([i for i in range(0,len(code),8) if code[i:i+8]!=original[i:i+8]]==[offset],
                 'mutation is not one word: '+name)
            codefile.write_bytes(code)
            decoded=subprocess.run([str(a.decoder),'-m','gf100','-V','gk104','-i','-n',str(codefile)],
                                   capture_output=True,timeout=20)
            need(decoded.returncode==0,'decode failed: '+name)
            text=decoded.stdout.decode();need(verify_decoder(code,text,a.decoder),'decoder differs: '+name)
            line=next((line for line in text.splitlines() if line.startswith('%08x:'%offset)),None)
            need(line is not None and line.endswith(operation),'unexpected decoded operation: '+name)
            decision=analyze(code,text,air)
            need(decision['status']=='REFUSED' and not decision['certificate_authorized'] and
                 any(row['reason']==reason for row in decision['refusals']), 'counterexample not refused: '+name)
            results.append({'name':name,'changed_offset':offset,'expected_reason':reason,
                            'synthetic_program_SHA256':sha(code),'synthetic_listing_SHA256':sha(decoded.stdout),
                            'refused':True})
    result={'status':'PASS','source_program_SHA256':sha(original),'baseline':baseline,
            'assembler_SHA256':sha(a.assembler.read_bytes()),'decoder_SHA256':sha(a.decoder.read_bytes()),
            'analyzer_SHA256':sha(Path(analyze.__code__.co_filename).read_bytes()),'mutations':results,
            'other_captured_programs':siblings,
            'synthetic_code_compiler_provenance_established':False,'synthetic_GPU_dispatches':0,
            'reconvergence_entry_is_assumed':True,'certificate_authorized':False}
    with out.open('x') as stream:json.dump(result,stream,indent=2,sort_keys=True);stream.write('\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
