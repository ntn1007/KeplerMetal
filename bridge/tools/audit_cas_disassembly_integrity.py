#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck a local CAS decoder-coverage counterexample without GPU execution."""
import argparse
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path
from recognize_native_cas import air_contract, recognize, sass_contract, verify_decoder

PREVIOUS = '9aa30b458263eeeddb782cd2a3b10ac362b6faf3ced9cbca805e55b515bebbee'
def sha(data): return hashlib.sha256(data).hexdigest()
def require(value, message):
    if not value: raise ValueError(message)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--previous-recognizer', type=Path, required=True)
    p.add_argument('--cases', type=Path, required=True)
    p.add_argument('--consumer-code', type=Path, required=True)
    p.add_argument('--consumer-listing', type=Path, required=True)
    p.add_argument('--decoder', type=Path, required=True)
    a = p.parse_args()
    old_bytes = a.previous_recognizer.read_bytes()
    require(sha(old_bytes)==PREVIOUS, 'Previous recognizer identity differs')
    spec = importlib.util.spec_from_file_location('previous_cas_recognizer', a.previous_recognizer)
    old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
    cases = {}
    for name, expected in [('slot1',True),('permuted',True),('live_noise',True),('original_compare_control',False)]:
        before=old.recognize(a.cases/name); after=recognize(a.cases/name,a.decoder)
        require(before['qualified']==after['qualified']==expected, 'Archived outcome differs: '+name)
        cases[name]={'qualified':expected,'native_SHA256':after['hashes']['native.sass'],'listing_SHA256':after['hashes']['native.asm']}
    source=(a.cases/'slot1/native.sass').read_bytes(); code=a.consumer_code.read_bytes(); text=a.consumer_listing.read_text()
    require(len(source)==len(code) and [i for i in range(0,len(code),8) if source[i:i+8]!=code[i:i+8]]==[0x2d8], 'Consumer is not the one-word fixture')
    rows=text.splitlines(); omitted=[i for i,s in enumerate(rows) if s.startswith('000002d8:') and s.endswith('mov b32 $r5 $r0')]; copy=[s for s in rows if s.startswith('000002e0:')]
    require(len(omitted)==len(copy)==1, 'Fixture listing differs')
    changed=rows.copy();changed[omitted[0]]=copy[0]; altered='\n'.join(changed)+'\n'
    opcode_tamper=text.replace('000002d8: 00015de4 28000000     mov b32 $r5 $r0','000002d8: 00015de4 28000000     nop')
    require(opcode_tamper!=text, 'Opcode alteration was not applied')
    air=air_contract(json.loads((a.cases/'slot1/typed-air.json').read_text()))
    require(air['qualified'] and air['expected_output_component']==0, 'AIR fixture differs')
    original_before=old.sass_contract(code,text,0); forged_before=old.sass_contract(code,altered,0)
    original_after=sass_contract(code,text,0); forged_after=sass_contract(code,altered,0)
    require(not original_before['qualified'] and forged_before['qualified'] and not original_after['qualified'] and not forged_after['qualified'] and 'offsets' in forged_after['reason'], 'Expected counterexample differs')
    require(sass_contract(code,opcode_tamper,0)['qualified'] and verify_decoder(code,text,a.decoder) and not verify_decoder(code,opcode_tamper,a.decoder) and not verify_decoder(code,altered,a.decoder) and not verify_decoder(code,text,None), 'Decoder authentication controls differ')
    with tempfile.TemporaryDirectory(prefix='kepler-cas-audit-') as folder:
        trial=Path(folder)
        for name in ('test.metal','test.air','test.metallib','typed-air.json'):
            (trial/name).write_bytes((a.cases/'slot1'/name).read_bytes())
        (trial/'native.sass').write_bytes(code)
        for candidate in (altered,opcode_tamper):
            (trial/'native.asm').write_text(candidate)
            require(old.recognize(trial)['qualified'] and not recognize(trial,a.decoder)['qualified'], 'Full qualification gate differs')
    print(json.dumps({'status':'PASS','previous_recognizer_SHA256':PREVIOUS,
      'current_recognizer_SHA256':sha(Path(__file__).with_name('recognize_native_cas.py').read_bytes()),
      'consumer_code_SHA256':sha(code),'complete_listing_SHA256':sha(text.encode()),'altered_listing_SHA256':sha(altered.encode()),
      'omitted_offset':'0x2d8','duplicated_offset':'0x2e0','previous_complete_qualified':False,'previous_altered_qualified':True,
      'current_complete_qualified':False,'current_altered_qualified':False,'current_refusal':forged_after['reason'],
      'structural_parser_accepts_forged_opcode':True,'pinned_decoder_rejects_forged_opcode':True,'missing_decoder_refused':True,
      'previous_full_policy_accepted_both_corruptions':True,'current_full_policy_refused_both_corruptions':True,
      'pinned_decoder_SHA256':sha(a.decoder.read_bytes()),'opcode_tampered_listing_SHA256':sha(opcode_tamper.encode()),
      'AIR_fixture_qualified':True,'archived_cases':cases,'GPU_execution':False,
      'scope':'Artificial one-instruction program and altered listing; no evidence of a defective disassembler or a GPU execution'},indent=2,sort_keys=True))

if __name__=='__main__':main()
