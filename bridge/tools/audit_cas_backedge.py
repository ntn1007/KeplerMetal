#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Offline-only, decoder-checked CAS backedge counterexample and regressions."""
import argparse, hashlib, importlib.util, json, shutil, tempfile
from pathlib import Path
from recognize_native_cas import recognize, verify_decoder
PREVIOUS='2dcd61e6a0205089d0ef6cc94b93d2c7de584984e48e0c43f14eeeb20686713a'

def sha(b):return hashlib.sha256(b).hexdigest()
def need(v,why):
 if not v:raise ValueError(why)
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('previous','cases','code','listing','decoder','out'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required')
 need(sha(a.previous.read_bytes())==PREVIOUS,'previous recognizer mismatch')
 spec=importlib.util.spec_from_file_location('previous_cas_recognizer',a.previous);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
 archived=[]
 for name,expected in [('slot1',True),('permuted',True),('live_noise',True),('original_compare_control',False)]:
  before=old.recognize(a.cases/name,a.decoder);after=recognize(a.cases/name,a.decoder)
  need(before['qualified']==after['qualified']==expected and before['decoder_reproduced_listing'] and after['decoder_reproduced_listing'],'archived verdict '+name)
  archived.append({'name':name,'qualified':expected,'native_SHA256':after['hashes']['native.sass']})
 source=(a.cases/'slot1/native.sass').read_bytes();code=a.code.read_bytes();text=a.listing.read_text()
 need(len(source)==len(code) and [i for i in range(0,len(code),8) if source[i:i+8]!=code[i:i+8]]==[0x2d8],'expected one changed instruction')
 need(any(s.startswith('000002d8:') and s.endswith('bra 0x250') for s in text.splitlines()),'backedge listing')
 need(verify_decoder(code,text,a.decoder),'pinned decoder mismatch')
 with tempfile.TemporaryDirectory(prefix='kepler-cas-backedge-audit-') as directory:
  d=Path(directory)
  for n in ('test.metal','test.air','test.metallib','typed-air.json'):shutil.copyfile(a.cases/'slot1'/n,d/n)
  (d/'native.sass').write_bytes(code);(d/'native.asm').write_text(text)
  before=old.recognize(d,a.decoder);after=recognize(d,a.decoder)
  need(before['AIR']['qualified'] and before['decoder_reproduced_listing'] and before['qualified'] and after['AIR']['qualified'] and after['decoder_reproduced_listing'] and not after['qualified'],'counterexample verdict')
  need(before['SASS']['CAS_load_offset']==0x250 and before['SASS']['redirect_offset']==0x2d0,'backedge target and redirect')
 result={'status':'PASS','previous_SHA256':PREVIOUS,'updated_SHA256':sha(Path(__file__).with_name('recognize_native_cas.py').read_bytes()),'decoder_SHA256':sha(a.decoder.read_bytes()),'synthetic_backedge_previous_accepted':True,'synthetic_backedge_updated_accepted':False,'synthetic_code_SHA256':sha(code),'synthetic_listing_SHA256':sha(text.encode()),'mutated_word_offset':'0x2d8','branch_target':'0x250','original_AIR_and_mutated_code_are_not_proven_related':True,'prior_cases':archived,'GPU_dispatches':0}
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(result,indent=2))
if __name__=='__main__':main()
