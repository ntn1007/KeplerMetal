#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline replay of predicated-exit counterexamples; never dispatch GPU code."""
import argparse,hashlib,importlib.util,json,subprocess,tempfile
from pathlib import Path
from recognize_native_cas import air_contract,verify_decoder
from trace_native_cas_flow import analyze

def sha(x):return hashlib.sha256(x).hexdigest()
def need(x,message):
    if not x:raise ValueError(message)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('previous','diagnosis','assembler','decoder','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();d=a.diagnosis.resolve();out=a.out.resolve();need(not out.exists() and out.parent.is_dir(),'fresh output required')
    previous=a.previous.read_bytes();need(sha(previous)=='861c44dbfedbc4580cf55de59a64ad6e784009f2a6d152af119da7fbbe149256','previous analyzer differs')
    spec=importlib.util.spec_from_file_location('prior_flow',a.previous);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    code=(d/'native.sass').read_bytes();listing=(d/'native.asm').read_text();typed=(d/'typed-air.json').read_bytes();state=json.loads((d/'diagnosis.json').read_text())
    need(sha(code)=='f16bf16da56d5dc060429f6886d2e1d80eafa0a960f48b7d776a3234fb6bcb41' and sha(code)==state['artifact_SHA256']['native.sass'] and sha(typed)==state['artifact_SHA256']['typed-air.json'],'snapshot differs')
    need(sha(a.assembler.read_bytes())=='1f023d5e1f0a5afc3a04510e264159923dac3182139e03c0a67600b9b1d4428e' and verify_decoder(code,listing,a.decoder),'tools or decoder differ')
    air=air_contract(json.loads(typed),state['function']);need(air==state['AIR'] and air['qualified'],'AIR differs')
    before=old.analyze(code,listing,air);after=analyze(code,listing,air);need(before==after and before['status']=='HYPOTHESIS_ONLY' and not before['certificate_authorized'],'historical observation differs')
    rows=[]
    with tempfile.TemporaryDirectory(prefix='kepler-predicated-control-') as directory:
        tmp=Path(directory)
        for name,operation in (('predicate_true','$p1 exit'),('predicate_false','(not $p1) exit')):
            src=tmp/(name+'.easm');assembled=tmp/(name+'.bin');program=tmp/(name+'.sass');src.write_text('.section #code 0;\n.skip 0x3d8;\nlong '+operation+';\n')
            ar=subprocess.run([str(a.assembler),'-m','gf100','-V','gk104','-i','-o',str(assembled),str(src)],capture_output=True,timeout=20);need(ar.returncode==0,'assembly failed')
            raw=assembled.read_bytes();need(len(raw)>=0x3e0,'assembled word missing');mut=bytearray(code);mut[0x3d8:0x3e0]=raw[0x3d8:0x3e0];mut=bytes(mut);need([i for i in range(0,len(code),8) if code[i:i+8]!=mut[i:i+8]]==[0x3d8],'mutation differs');program.write_bytes(mut)
            run=subprocess.run([str(a.decoder),'-m','gf100','-V','gk104','-i','-n',str(program)],capture_output=True,timeout=20);need(run.returncode==0,'decoder failed');text=run.stdout.decode();need(verify_decoder(mut,text,a.decoder) and any(row.startswith('000003d8:') and row.endswith(operation) for row in text.splitlines()),'decoded instruction differs')
            prior=old.analyze(mut,text,air);current=analyze(mut,text,air);need(prior['status']=='HYPOTHESIS_ONLY' and not prior['certificate_authorized'] and current['status']=='REFUSED' and not current['certificate_authorized'] and any(x['reason']=='unsupported control flow in tracked slice' for x in current['refusals']),'verdict differs')
            rows.append({'name':name,'operation':operation,'synthetic_program_sha256':sha(mut),'decoded_listing_sha256':sha(run.stdout),'previous_status':prior['status'],'current_status':current['status']})
    result={'status':'PASS_PREDICATED_CAS_CONTROL','previous_analyzer_sha256':sha(previous),'current_analyzer_sha256':sha(Path(analyze.__code__.co_filename).read_bytes()),'original_program_sha256':sha(code),'original_result_unchanged':True,'mutated_offset':'0x3d8','counterexamples':rows,'synthetic_air_sass_compiler_correspondence_proved':False,'decoder_semantics_proved':False,'gpu_dispatches':0,'certificate_authorized':False,'system_modified':False}
    with out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(result,indent=2))
if __name__=='__main__':main()
