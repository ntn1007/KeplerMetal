#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare vector-span safety against the previous recognizer and retained diagnoses."""
import argparse, hashlib, importlib.util, json, sys
from pathlib import Path
from recognize_native_cas import register_references, sass_contract, verify_decoder
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests'))
from test_native_cas_recognizer import listing
PREVIOUS='fea02920403b9598e78d09a2ed83ea3b00e4be273e9e4f344036e8fa5a49ee24'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(v,why):
 if not v:raise ValueError(why)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--previous',type=Path,required=True);p.add_argument('--generated',type=Path,required=True);p.add_argument('--decoder',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'Fresh output required');need(sha(a.previous)==PREVIOUS,'Previous recognizer hash differs')
 spec=importlib.util.spec_from_file_location('old_cas_recognizer',a.previous);old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
 synthetic=[]
 for op,expect_old,expect_new in [('mov b64 $r20d $r23d',True,False),('mov b128 $r20q $r22q',True,False),('mov b128 $r20q $r20q',True,True)]:
  code,text=listing(extra=op);before=old.sass_contract(code,text,0);after=sass_contract(code,text,0);need(before['qualified']==expect_old and after['qualified']==expect_new,'Synthetic outcome differs')
  if not expect_new:need('floor24' in after['reason'],'Wrong refusal reason')
  synthetic.append({'operation':op,'expanded_registers':sorted(register_references(op)),'previous_qualified':before['qualified'],'current_qualified':after['qualified']})
 manifest=json.loads((a.generated/'KeplerNativeCAS/assets/client-manifest.json').read_text());actual=[]
 for row in manifest['profiles']:
  if not row['candidate']:continue
  d=a.generated/('diagnosis-'+row['function']);state=json.loads((d/'diagnosis.json').read_text());code=(d/'native.sass').read_bytes();text=(d/'native.asm').read_text();need(verify_decoder(code,text,a.decoder),'Decoder mismatch: '+row['function'])
  before=old.sass_contract(code,text,state['AIR']['expected_output_component']);after=sass_contract(code,text,state['AIR']['expected_output_component']);need(before==after==state['SASS'] and after['qualified'],'Historical diagnosis changed: '+row['function'])
  actual.append({'function':row['function'],'native_SHA256':sha(d/'native.sass'),'max_explicit_register':after['max_explicit_register'],'before_after_equal':True})
 need(len(actual)==4,'Expected four candidates')
 result={'status':'PASS','previous_recognizer_SHA256':PREVIOUS,'current_recognizer_SHA256':sha(Path(__file__).with_name('recognize_native_cas.py')),'synthetic':synthetic,'historical_candidates':actual,'GPU_dispatch':False,'scope':'Synthetic listing controls are not validated hardware instructions; exact retained native candidates are rechecked offline, not freshly GPU-qualified.'}
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps({'status':'PASS','synthetic_controls':len(synthetic),'historical_candidates':len(actual),'GPU_dispatch':False},sort_keys=True))
if __name__=='__main__':main()
