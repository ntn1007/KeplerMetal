#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline-only one-word reconvergence counterexamples and archived CAS regressions."""
import argparse,hashlib,importlib.util,json,shutil,subprocess,tempfile
from pathlib import Path
from recognize_native_cas import recognize,verify_decoder
PREVIOUS='a1a5a7edc7828b5a05a12b14835049f59d0692ae45393bc26ac18e2fa6373a6a'

def sha(b):return hashlib.sha256(b).hexdigest()
def need(v,why):
 if not v:raise ValueError(why)
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('previous','cases','assembler','decoder','out'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required');need(sha(a.previous.read_bytes())==PREVIOUS,'previous recognizer differs')
 need(sha(a.assembler.read_bytes())=='1f023d5e1f0a5afc3a04510e264159923dac3182139e03c0a67600b9b1d4428e','assembler differs')
 spec=importlib.util.spec_from_file_location('previous_recognizer',a.previous);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old);archived=[]
 for name,expected in [('slot1',True),('permuted',True),('live_noise',True),('original_compare_control',False)]:
  before=old.recognize(a.cases/name,a.decoder);after=recognize(a.cases/name,a.decoder);need(before['qualified']==after['qualified']==expected and before['decoder_reproduced_listing'] and after['decoder_reproduced_listing'],'archived verdict '+name);archived.append({'name':name,'qualified':expected,'native_SHA256':after['hashes']['native.sass']})
 source=(a.cases/'slot1/native.sass').read_bytes();original_listing=(a.cases/'slot1/native.asm').read_text();need(verify_decoder(source,original_listing,a.decoder),'source decode differs')
 variants=[('enter_compare',0x238,'joinat 0x2c8'),('enter_lock',0x238,'joinat 0x258'),('enter_compare_schedule',0x238,'joinat 0x2c0'),('enter_from_loop',0x2b8,'joinat 0x260'),('nested_same_target',0x238,'joinat 0x280')];results=[]
 with tempfile.TemporaryDirectory(prefix='kepler-cas-incoming-') as directory:
  t=Path(directory)
  for n in ('test.metal','test.air','test.metallib','typed-air.json'):shutil.copyfile(a.cases/'slot1'/n,t/n)
  for name,offset,operation in variants:
   src=t/(name+'.easm');assembled=t/(name+'.bin');src.write_text('.section #code 0;\n.skip %#x;\nlong %s;\n'%(offset,operation))
   run=subprocess.run([str(a.assembler),'-m','gf100','-V','gk104','-i','-o',str(assembled),str(src)],capture_output=True,timeout=20);need(run.returncode==0,'assembly failed '+name);data=assembled.read_bytes();need(len(data)>=offset+8,'assembled word missing')
   modified=bytearray(source);modified[offset:offset+8]=data[offset:offset+8];code=bytes(modified);need([i for i in range(0,len(source),8) if source[i:i+8]!=code[i:i+8]]==[offset],'one-word mutation differs '+name);(t/'native.sass').write_bytes(code)
   dec=subprocess.run([str(a.decoder),'-m','gf100','-V','gk104','-i','-n',str(t/'native.sass')],capture_output=True,timeout=20);need(dec.returncode==0,'decode failed '+name);text=dec.stdout.decode();need(verify_decoder(code,text,a.decoder) and any(x.startswith('%08x:'%offset) and x.endswith(operation) for x in text.splitlines()),'decoded instruction differs '+name);(t/'native.asm').write_text(text)
   before=old.recognize(t,a.decoder);after=recognize(t,a.decoder);need(before['qualified'] and before['AIR']['qualified'] and before['decoder_reproduced_listing'] and not after['qualified'] and after['AIR']['qualified'] and after['decoder_reproduced_listing'],'verdict differs '+name)
   results.append({'name':name,'offset':hex(offset),'operation':operation,'synthetic_program_sha256':sha(code),'listing_sha256':sha(dec.stdout),'previous_qualified':True,'updated_qualified':False})
 result={'status':'PASS_CAS_RECONVERGENCE_GUARD','previous_recognizer_sha256':PREVIOUS,'current_recognizer_sha256':sha(Path(recognize.__code__.co_filename).read_bytes()),'assembler_sha256':sha(a.assembler.read_bytes()),'decoder_sha256':sha(a.decoder.read_bytes()),'original_program_sha256':sha(source),'counterexamples':results,'archived_cases':archived,'synthetic_air_sass_compiler_correspondence_proved':False,'decoder_semantics_proved':False,'gpu_dispatches':0,'system_modified':False}
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
