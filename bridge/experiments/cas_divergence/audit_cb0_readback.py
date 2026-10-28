#!/usr/bin/env python3
"""Independently audit two pinned CB0 witness/control pairs."""
import argparse
import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path
from analyze_indirect import sections
from run_repair import PINS,SYSTEM

HERE=Path(__file__).resolve().parent
BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'tools'))
from recognize_native_cas import verify_decoder

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def need(ok,reason):
    if not ok:raise ValueError(reason)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--builds',nargs=2,type=Path,required=True);p.add_argument('--runs',nargs=4,type=Path,required=True)
    for name in ('container','decoder','out'):p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();out=a.out.resolve();need(not out.exists() and out.parent.is_dir(),'fresh output required')
    blob=a.container.read_bytes();need(hashlib.sha256(blob).hexdigest()=='adc3551baff3d2e6de1e06fd158b80d9fe6f15df744d9e28b40dfe92de327821','capture differs')
    parts=sections(blob);table=parts[0x10006];need(len(table)==12 and hashlib.sha256(table).hexdigest()=='6b6731dc9464fd825d2aefe82c37334875811491ee9c774bae6460f0008949ef','table differs')
    candidate=list(struct.unpack('<III',table));need(candidate==[0x298,0x2b8,0x330],'candidate values differ')
    builds=[x.resolve() for x in a.builds];expected={'control':'e7d58f3637b4268c97d2e0a6ec94d9177833ac2747db954b6ec6be37161d4d7e',
                  'cb0':'60291c5a9dde52384a97a31d1edff5c6374d12a1d40a3abfdbd0ed3484099625'}
    for build in builds:
        manifest=json.loads((build/'build.json').read_text())
        for name,digest in manifest['files_SHA256'].items():need(sha(build/name)==digest,'build differs: '+name)
        need(sha(build/'shader.metallib')==PINS['shader.metallib'] and sha(build/'original.sass')==PINS['original.sass'] and
             (build/'original.sass').read_bytes()==parts[0x10005] and
             sha(build/'native.metadata')=='f99b8ca94aec90088ba8aee80c42b9e242a7829a81c3fedbf34b2312b08bacbe' and
             sha(build/'KeplerNativeCAS.mm')==sha(BRIDGE/'src/KeplerNativeCAS.mm') and
             sha(build/'src/KeplerConditionalAux.h')==sha(BRIDGE/'src/KeplerConditionalAux.h') and
             sha(build/'src/KeplerNativeCASAdapter.inc')==sha(BRIDGE/'src/KeplerNativeCASAdapter.inc'),'runtime or capture differs')
        for source in ('cb0_readback_host.mm','cb0_readback_import.mm'):need(sha(build/source)==sha(HERE/source),'host source differs')
        orig=(build/'original.sass').read_bytes()
        for mode,digest in expected.items():
            code=(build/(mode+'.sass')).read_bytes()
            need(sha(build/(mode+'.sass'))==digest and len(code)==len(orig)+64 and
                 [i for i in range(0,len(orig),8) if orig[i:i+8]!=code[i:i+8]]==[0x528] and
                 code[0x560:0x568]==orig[0x528:0x530] and
                 verify_decoder(code,(build/(mode+'.asm')).read_text(),a.decoder),'witness code differs')
    need(sha(builds[0]/'host')==sha(builds[1]/'host'),'independent host rebuild differs')
    receipts=[];intervals=[]
    for index,root in enumerate(a.runs):
        root=root.resolve();build=builds[index//2];mode=('control','cb0')[index%2]
        m=json.loads((root/'manifest.json').read_text());report=json.loads((root/'report.json').read_text())
        need(m['mode']==mode and m['exit_code']==0 and m['GPU_reservation']['state']=='terminal' and
             not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and m['system_before']==m['system_after']==SYSTEM and
             m['build_sha256']==sha(build/'build.json') and m['original_binary_sha256']==sha(build/'host') and
             m['signed_binary_sha256']==sha(root/'application'),'process evidence differs')
        need(subprocess.run(['codesign','--verify','--strict',str(root/'application')],capture_output=True,timeout=15).returncode==0,'signature differs')
        need(report['status']=='COMPLETED' and report['mode']==mode and report['GPU_dispatch'] and
             report['device']=='NVIDIA GeForce GTX 880M' and report['registry_id']==4294968416 and
             report['command_status']==4 and (report['threads'],report['groups'],report['pattern'],report['variant'],report['seed'])==(33,3,0,1,0x1234),
             'GPU report differs')
        proof=report['import'];events=proof['events']
        need(proof['contract_verified'] and proof['constructor_restored'] and len(events)==1 and
             events[0]['conditional_auxiliary_section_pinned'] and events[0]['expected_original_code_identical'] and
             events[0]['native_metadata_identical_to_certificate'] and events[0]['imported_code_identical'] and
             events[0]['native_metadata_preserved_except_instruction_count'] and events[0]['code_input_unchanged_after_constructor'],
             'constructor receipt differs')
        raw=(root/'output.bin').read_bytes();need(len(raw)==1712 and raw[:64]==b'\xa5'*64 and raw[-64:]==b'\xa5'*64,'output guard differs')
        wanted=[0x111,0x222,0x333] if mode=='control' else candidate
        for lane in range(99):
            row=struct.unpack_from('<4I',raw,64+16*lane)
            need(list(row[:3])==wanted and row[3]==(lane^0x6d2b79f5),'CPU oracle mismatch')
        verified=json.loads((root/'verified.json').read_text())
        need(verified['status']=='PASS' and verified['output_sha256']==sha(root/'output.bin') and verified['triplet']==wanted,
             'saved verifier differs')
        receipts.append({'mode':mode,'GPU_rows':99,'checked_words':396,'output_sha256':sha(root/'output.bin'),
                         'signed_host_sha256':m['signed_binary_sha256'],'triplet':wanted})
        intervals.append((m['started_at'],m['completed_at']))
    intervals.sort();need(all(s<=e for s,e in intervals) and all(intervals[i][1]<=intervals[i+1][0] for i in range(3)),'process overlap')
    result={'status':'PASS','pairs':2,'receipts':receipts,'candidate_section_sha256':hashlib.sha256(table).hexdigest(),
            'CB0_gpu_values_match_captured_section':True,'indirect_branch_execution_proved':False,
            'unmodified_shader_execution_proved_by_this_witness':False,'resident_instructions_read_back':False,
            'all_patterns_proved':False,'performance_benchmark':False}
    with out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps(result))

if __name__=='__main__':main()
