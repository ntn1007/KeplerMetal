#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit one historical AMD key reference; no vendor code is executed."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

EXPECTED = '0b288cd12e22f0ba40a241dbf42a6a00d779e1a028d670f73c1e487229711f86'
NAME = './System/Library/Extensions/AMDRadeonX3000.kext/Contents/MacOS/AMDRadeonX3000'
REGION = '4e3a0798d174fdcf8afffa87ad087ec128e98fb2ce8c2cd48d6e1ff75070dabc'
REA = '217c6cf96a1322809406ab5b66f57508091788b5a437226bbba16c2860a23329'
IDS = ('ev_b10f0527b93cd766fd36e523447f865bbafcf6baa6082d192b85547231e84a32',
       'ev_a4f49e7d46190b9e619c7a4263b9f56f23feec47a73105114bc82bd28327178a',
       'ev_889ff8a572c35eeb0eb2be6b99d8b0e4a92a16b3c4aa766273ba125c9615b287',
       'ev_a22bcc92ae3dfcfa641e48868f39172375b5b38984d3f544ac81b0302aede469')


def sha(data): return hashlib.sha256(data).hexdigest()
def need(value, message):
    if not value: raise ValueError(message)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('binary','survey','rea','out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    need(a.out.parent.is_dir() and not a.out.exists(), 'fresh output required')
    binary = a.binary.read_bytes(); survey = json.loads(a.survey.read_text()); evidence = a.rea.read_bytes()
    rows = [r for r in survey['matches'] if r['name'] == NAME]
    need(survey['status'] == 'PASS_FULL_REGULAR_MEMBER_LITERAL_SURVEY' and len(rows) == 1 and
         rows[0]['sha256'] == sha(binary) == EXPECTED and rows[0]['size'] == len(binary) == 6698064,
         'survey/binary identity differs')
    need(sha(evidence) == REA, 'REA bundle differs')
    records = json.loads(evidence)['records']
    selected = []
    for eid in IDS:
        found = [r for r in records if r.get('evidence_id') == eid]
        need(len(found) == 1 and found[0]['subject']['digest']['sha256'] == EXPECTED, 'REA identity differs')
        selected.append(found[0])
    need(any(x.get('address') == '0x110015' and x.get('value') == 'IOGVACodec' for x in selected[0]['normalized_result']), 'REA string differs')
    need('0xcd2' in selected[1]['normalized_result'], 'REA reference differs')
    proc = selected[2]['normalized_result'];need(proc['found'] and proc['procedure']['address'] == '0x93e', 'REA procedure differs')
    asm = selected[3]['normalized_result']['assembly']
    for instruction in ('0xcbe: CMP byte ptr [RAX + 0x6d], 0x0', '0xcc2: JZ 0x00000d03',
                        '0xcc4: CMP dword ptr [R13 + 0x2508], 0x5', '0xccc: JNZ 0x00000d03',
                        '0xcd2: LEA RSI, [0x110015]', '0xcd9: LEA R12, [0x110020]',
                        '0xce3: MOV RDX, R12', '0xce6: CALL qword ptr [RAX + 0x270]'):
        need(instruction in asm, 'REA instruction differs')
    need(sha(binary[0xcbe:0xd03]) == REGION and binary[0x110015:0x110024] == b'IOGVACodec\0VCE\0', 'code or string window differs')
    headers = subprocess.check_output(['xcrun','llvm-objdump','--macho','--private-headers',str(a.binary)], text=True, timeout=60)
    need(re.search(r'segname __TEXT\s+vmaddr 0x0+\s+vmsize .*\s+fileoff 0',headers), 'text mapping differs')
    names = subprocess.check_output(['xcrun','llvm-nm','-n',str(a.binary)], text=True, timeout=60)
    need(re.search(r'^0000000000220a50\s+S\s+__ZTV37AMDRadeonX3000_AMDGraphicsAccelerator$',names,re.M), 'vtable symbol differs')
    reloc = subprocess.check_output(['xcrun','llvm-objdump','--macho','--reloc',str(a.binary)], text=True, timeout=60)
    need(re.search(r'^00220cd0\s+False\s+quad\s+True\s+UNSIGND\s+False\s+__ZN15IORegistryEntry11setPropertyEPKcS1_$',reloc,re.M),
         'vtable relocation differs')
    receipt = {'status':'PASS_AMD_STATIC_PROPERTY_PATH', 'survey_sha256':sha(a.survey.read_bytes()),
        'binary_sha256':EXPECTED, 'rea_bundle_sha256':REA, 'rea_evidence_ids':list(IDS),
        'function_start':'0x93e', 'key_reference':'0xcd2', 'value_reference':'0xcd9',
        'key':'IOGVACodec', 'amd_value':'VCE', 'conditional_byte_offset':'0x6d',
        'conditional_integer_offset':'0x2508', 'conditional_integer_value':5,
        'virtual_call':'0xce6', 'vtable_symbol':'0x220a50', 'vtable_slot_relocation':'0x220cd0',
        'relocated_symbol':'IORegistryEntry::setProperty(char const*, char const*)',
        'code_window_sha256':REGION, 'dynamic_call_target_proved':False, 'amd_runtime_tested':False,
        'nvidia_value_proved':False, 'hardware_video_execution_proved':False,
        'vendor_execution':False, 'GPU_execution':False, 'system_modified':False,
        'audit_sha256':sha(Path(__file__).read_bytes())}
    with a.out.open('x') as f:
        json.dump(receipt, f, indent=2, sort_keys=True);f.write('\n')
    print(json.dumps({'status':receipt['status'], 'amd_value':receipt['amd_value'], 'nvidia_value_proved':False}))


if __name__ == '__main__': main()
