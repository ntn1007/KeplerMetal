#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare a pinned historical NVIDIA startup property path with AMD evidence."""
import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path

BIN='25a0bccd7caa884d6aa964743b35f879ec326c46d255dc6212c47e7a20f6f38e'
REA='46aa49d2e7cf972a95bf92140acd071eccd7f51ee3a4c921d94574e3915c070e'
EVIDENCE='ev_7d3ad8f078aa03b6c531dec6bc08bc50c0b1b8f228ecf900c9c70c28d4bdf795'
AMD='50bead22d803bd024f9dd0e7847733aa5c7d5201328558f43c7e96d501f7804b'
SURVEY='09314e94e288a088ac761b61e6fe7a0bac2967dc93478b8454b7c912d7a15834'


def sha(b): return hashlib.sha256(b).hexdigest()
def need(v,msg):
    if not v: raise ValueError(msg)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('binary','survey','rea','amd','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();need(a.out.parent.is_dir() and not a.out.exists(),'fresh output required')
    data=a.binary.read_bytes(); rb=a.rea.read_bytes(); ab=a.amd.read_bytes(); sb=a.survey.read_bytes()
    need(sha(data)==BIN and sha(rb)==REA and sha(ab)==AMD,'input digest differs')
    survey=json.loads(sb);amd=json.loads(ab)
    need(survey['status']=='PASS_SIERRA_REGULAR_MEMBER_LITERAL_SURVEY' and survey['archive_sha256']==SURVEY and
         survey['records']==105031 and survey['regular_members']==70898 and len(survey['matches'])==14 and
         not any('/GeForce' in r['name'] or '/NVDA' in r['name'] for r in survey['matches']), 'survey differs')
    need(amd['status']=='PASS_AMD_STATIC_PROPERTY_PATH' and amd['key']=='IOGVACodec' and amd['amd_value']=='VCE' and not amd['nvidia_value_proved'],'AMD evidence differs')
    records=[r for r in json.loads(rb)['records'] if r.get('evidence_id')==EVIDENCE]
    need(len(records)==1 and records[0]['subject']['digest']['sha256']==BIN,'REA evidence differs')
    proc=records[0]['normalized_result']['procedure'];asm=records[0]['normalized_result']['assembly']
    need(proc['address']=='0x5420' and proc['name']=='__ZN13nvAccelerator5startEP9IOService','REA function differs')
    for line in ('0x5757: MOV RAX, qword ptr [R15]', '0x575a: LEA RSI, [0x718b2]',
                 '0x5761: MOV EDX, 0x3', '0x5766: MOV ECX, 0x20',
                 '0x576b: MOV RDI, R15', '0x576e: CALL qword ptr [RAX + 0x280]'):
        need(line in asm,'REA instruction differs')
    need(data[0x718b2:0x718c2]==b'NVDA,mm-version\0' and
         sha(data[0x5757:0x5774])=='cdfaeffeb0ecf2572be2e2d7dab8bfffc03e7a69c9f496fd3269440ad8f7103d', 'code window differs')
    nm=subprocess.check_output(['xcrun','llvm-nm','-n',str(a.binary)],text=True,timeout=60)
    need(re.search(r'^0000000000077ac8\s+S\s+__ZTV13nvAccelerator$',nm,re.M),'vtable symbol differs')
    reloc=subprocess.check_output(['xcrun','llvm-objdump','--macho','--reloc',str(a.binary)],text=True,timeout=60)
    need(re.search(r'^00077d58\s+False\s+quad\s+True\s+UNSIGND\s+False\s+__ZN15IORegistryEntry11setPropertyEPKcyj$',reloc,re.M),'vtable relocation differs')
    result={'status':'PASS_STATIC_NVIDIA_PROPERTY_COMPARISON','nvidia_binary_sha256':BIN,
        'sierra_survey_sha256':sha(sb),'amd_audit_sha256':AMD,'rea_bundle_sha256':REA,'rea_evidence_id':EVIDENCE,
        'nvidia_start':'0x5420','nvidia_key':'NVDA,mm-version','nvidia_value':3,'nvidia_integer_width':32,
        'nvidia_call':'0x576e','nvidia_vtable':'0x77ac8','nvidia_relocation':'0x77d58',
        'nvidia_relocated_symbol':'IORegistryEntry::setProperty(char const*, unsigned long long, unsigned int)',
        'amd_key':'IOGVACodec','amd_value':'VCE','nvidia_codec_value_proved':False,
        'dynamic_vtable_target_proved':False,'runtime_property_write_proved':False,
        'vendor_execution':False,'GPU_execution':False,'hardware_video_execution_proved':False,'system_modified':False,
        'audit_sha256':sha(Path(__file__).read_bytes())}
    with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'status':result['status'],'nvidia_key':result['nvidia_key'],'nvidia_codec_value_proved':False}))


if __name__=='__main__':main()
