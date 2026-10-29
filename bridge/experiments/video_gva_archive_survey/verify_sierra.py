#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Cross-check the Sierra survey, decoded payload and a known NVIDIA member."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE=Path(__file__).resolve().parent
ARCHIVE_SHA='09314e94e288a088ac761b61e6fe7a0bac2967dc93478b8454b7c912d7a15834'
NVIDIA_SHA='25a0bccd7caa884d6aa964743b35f879ec326c46d255dc6212c47e7a20f6f38e'
NAME='./System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce'


def sha(b):return hashlib.sha256(b).hexdigest()
def need(v,msg):
    if not v: raise ValueError(msg)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('archive','survey','payload-receipt','nvidia-audit','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();need(a.out.parent.is_dir() and not a.out.exists(),'fresh output required')
    sb=a.survey.read_bytes();pb=a.payload_receipt.read_bytes();nb=a.nvidia_audit.read_bytes()
    s=json.loads(sb);d=json.loads(pb);n=json.loads(nb)
    need(s['status']=='PASS_SIERRA_REGULAR_MEMBER_LITERAL_SURVEY' and s['archive_sha256']==ARCHIVE_SHA and
         s['archive_bytes']==5835166720==a.archive.stat().st_size and s['records']==105031 and s['regular_members']==70898 and
         s['scanner_sha256']==sha((HERE/'survey.py').read_bytes()) and s['wrapper_sha256']==sha((HERE/'sierra_survey.py').read_bytes()),'survey differs')
    need(d['status']=='PASS_PBZX_DECODE_IDENTITY' and d['decoded_sha256']==ARCHIVE_SHA and d['decoded_bytes']==s['archive_bytes'] and
         d['survey_sha256']==sha(sb) and d['verifier_sha256']==sha((HERE/'payload_identity.py').read_bytes()),'decoded payload differs')
    need(n['status']=='PASS_STATIC_NVIDIA_PROPERTY_COMPARISON' and n['nvidia_binary_sha256']==NVIDIA_SHA and n['sierra_survey_sha256']==sha(sb),'NVIDIA audit differs')
    rows=s['matches'];need(len(rows)==14 and not any('/GeForce' in r['name'] or '/NVDA' in r['name'] for r in rows),'matched paths differ')
    controls={r['plist_key_values'][0]['string'] for r in rows if r['plist_parse']=='ok' and len(r['plist_key_values'])==1}
    need(controls=={'Gen6','Gen7','Gen75','Gen8','Gen9','Gen95'} and s['oversize_plists']==0,'controls differ')
    member=subprocess.check_output(['bsdtar','-xOf',str(a.archive),NAME],timeout=180)
    need(sha(member)==NVIDIA_SHA and len(member)==932752,'archive NVIDIA member differs')
    result={'status':'PASS_SIERRA_SURVEY_CROSSCHECK','archive_sha256':ARCHIVE_SHA,'survey_sha256':sha(sb),
        'payload_receipt_sha256':sha(pb),'nvidia_audit_sha256':sha(nb),'nvidia_member_sha256':NVIDIA_SHA,
        'regular_members':s['regular_members'],'matching_members':len(rows),'intel_plist_control_values':len(controls),
        'payload_decompressed_match':True,'package_signature_rechecked':False,'nested_compression_searched':False,
        'nvidia_codec_value_proved':False,'dynamic_producers_excluded':False,'vendor_execution':False,
        'GPU_execution':False,'hardware_video_execution_proved':False,'system_modified':False,
        'verifier_sha256':sha(Path(__file__).read_bytes())}
    with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'status':result['status'],'matches':len(rows),'nvidia_member_match':True}))


if __name__=='__main__':main()
