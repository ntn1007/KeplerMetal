#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Qualify a pinned buffer-size helper and its guarded CPU execution.

No IOKit calls or GPU commands are issued. Vendor bytes stay in the private
output directory. Only this exact source-checked helper is executed.
"""
import argparse
import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools'))
from compare_video_profile import file_bytes
from video_method_contract import IO_SHA, get_buffer_evidence, static_contract

HERE=Path(__file__).resolve().parent
EXPECTED_BUNDLE='9635db888ec07284dadf3298cf16da5c89d4d64056a9077fa02e074c97368652'
HELPER_ID='ev_d2cf4c019488b13eab432078e37e85d8b9fa3c547f9958c38a62f2556aede5dc'
REGIONS={
 (0x9ede,0x9f6f):'1e5a4c35d4b28e5dca9e0b5c33c40e6a706b2b0447523fb9cfb275e1bac1954f',
 (0x9f70,0xa03b):'ae56e29ff9fa623fc4b8770880eaa6133b476e43b56650578b18e5a30269edbc',
 (0xadec,0xae6d):'ce9b1ea62eb27466752292710887201d5958d9451298bcb9e26462132719211f',
 (0x7c52,0x7d5d):'2a261a8c5fcc9590528afda765b639012af60a03cb11b581351e29aa167ef339'}

def sha(data): return hashlib.sha256(data).hexdigest()
def need(ok,msg):
    if not ok: raise ValueError(msg)
def run(label,args,out,expected=0):
    p=subprocess.run(list(map(str,args)),capture_output=True,timeout=60)
    (out/(label+'.stdout')).write_bytes(p.stdout); (out/(label+'.stderr')).write_bytes(p.stderr)
    need(p.returncode==expected and not p.stderr,label+' failed; inspect retained diagnostics')
    return p.stdout.decode()
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('ioaccel','geforce','prior-rea','get-buffer-rea','new-rea','out'):
        p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args(); need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required')
    contract=static_contract(a.ioaccel,a.geforce,a.prior_rea); get_buffer_evidence(a.get_buffer_rea)
    image=a.ioaccel.read_bytes(); bundle_bytes=a.new_rea.read_bytes()
    need(sha(image)==IO_SHA and sha(bundle_bytes)==EXPECTED_BUNDLE,'pinned image or evidence differs')
    regions={}
    for (start,end),digest in REGIONS.items():
        offset,data=file_bytes(image,start,end-start); need(sha(data)==digest,'code region changed')
        regions[hex(start)]={'end_exclusive':hex(end),'file_offset':offset,'bytes':len(data),'sha256':digest}
    records=json.loads(bundle_bytes)['records']
    matches=[r for r in records if r.get('evidence_id')==HELPER_ID and r.get('operation')=='analyze_function']
    need(len(matches)==1 and matches[0]['subject']['digest']['sha256']==IO_SHA and
         matches[0]['normalized_result']['procedure']['address']=='0x9ede' and
         matches[0]['normalized_result']['procedure']['body']['total_bytes']==145,'helper evidence differs')
    limit_rows=[r for r in json.loads(a.prior_rea.read_text())['records']
        if r.get('evidence_id')=='ev_99f570af976f00a966363ca531f34c8b84e8c4b27b684be9ba2af75b486f0575']
    need(len(limit_rows)==1,'limits evidence missing')
    limit=limit_rows[0]['normalized_result']['assembly']
    need(all(v in limit for v in ('0xae1f: MOV ECX, 0x10000','0xae28: MOV EDX, 0x80000',
         '0xae39: MOV dword ptr [RBX + 0x34], EAX','0xae60: MOV dword ptr [RBX + 0x64], EAX')),'limits differ')
    _,block=file_bytes(image,0x9f70,0xa03b-0x9f70)
    def at(address): return address-0x9f70
    need(block[at(0x9fd2)]==0x74 and 0x9fd4+struct.unpack_from('<b',block,at(0x9fd3))[0]==0xa031,
         'empty-list branch differs')
    need(block[at(0x9fff)]==0xe8 and 0xa004+struct.unpack_from('<i',block,at(0xa000))[0]==0x9ede,
         'helper call differs')
    need(contract['static_candidate_classes']['candidate_indices']==[0,1],'class profile differs')
    a.out.mkdir(); helper=a.out/'helper.private.bin'
    helper.write_bytes(file_bytes(image,0x9ede,145)[1])
    run('compiler',['xcrun','clang++','--version'],a.out)
    run('build',['xcrun','clang++','-std=c++17','-Wall','-Wextra','-Werror','-O1','-g',
        '-fsanitize=undefined','-fno-sanitize-recover=all',HERE/'compare.cpp','-o',a.out/'compare'],a.out)
    result=run('compare',[a.out/'compare',helper],a.out)
    need(result.startswith('PASS: 4096 original CPU helper comparisons'),'comparison result differs')
    wrong=a.out/'altered-helper.private.bin'; altered=bytearray(helper.read_bytes()); altered[0]^=1
    wrong.write_bytes(altered)
    run('tampered-control',[a.out/'compare',wrong],a.out,9)
    need(sha(helper.read_bytes())==REGIONS[(0x9ede,0x9f6f)],'helper changed')
    need(sha(a.ioaccel.read_bytes())==IO_SHA and sha(a.new_rea.read_bytes())==EXPECTED_BUNDLE,
         'inputs changed during validation')
    report={'status':'PASS_PINNED_BUFFER_SIZE_CPU','helper_evidence_id':HELPER_ID,'image_sha256':IO_SHA,
        'new_evidence_bundle_sha256':EXPECTED_BUNDLE,'code_regions':regions,'cases':4096,
        'class_candidates':[0,1],'initial_size_bytes':65536,'upper_size_bytes':524288,'growth_factor':2,
        'first_branch_skips_size_load':True,'branch_interpretation':'conditional static only, not live context',
        'source_sha256':{n:sha((HERE/n).read_bytes()) for n in ('audit.py','compare.cpp')},
        'cpu_helper_executed_on_synthetic_memory':True,'modified_helper_refused_before_execution':True,
        'gpu_connections_opened':False,'hardware_video_execution_proved':False,
        'system_modified':False}
    (a.out/'validation.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    print(json.dumps(report,sort_keys=True))
if __name__=='__main__': main()
