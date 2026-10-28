#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independently check the pinned CAS SDK hosts and their raw GPU outputs."""
import argparse
import base64
import hashlib
import json
import struct
import subprocess
from pathlib import Path


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def need(value,message):
    if not value:raise ValueError(message)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args();work=args.work.resolve();out=args.out.resolve()
    need(not out.exists() and out.parent.is_dir(),'fresh output required')
    build=json.loads((work/'sdk-build.json').read_text())
    need(sha(work/'probe')==build['probe_SHA256'] and
         sha(work/'src/KeplerNativeCASAdapter.inc')==build['adapter_SHA256'] and
         sha(work/'certificate.json')==build['certificate_SHA256'], 'SDK build input differs')
    tests=[('repaired-v1-l33-2',33,1),('repaired-v0-l33',33,0),
           ('repaired-v0-l128',128,0),('repaired-v1-l128',128,1),
           ('repaired-v1-l128-repeat',128,1),('repaired-v0-l1024',1024,0),
           ('repaired-v1-l1024',1024,1)]
    negative=['negative-pin-v1-l33-2','negative-trampoline','negative-profile','negative-metadata']
    receipts=[];intervals=[];operations=0;words=0
    for name,local,variant in tests:
        directory=work/name;manifest=json.loads((directory/'manifest.json').read_text())
        data=json.loads((directory/'execution.stdout').read_text())
        plan=json.loads((directory/'plan.json').read_text())
        check_host(directory,manifest,build,0)
        need(manifest['certificate_template_SHA256']==build['certificate_SHA256'], 'certificate template differs')
        need(plan['mode']=='native_repaired' and Path(plan['original_code']).name=='original.sass' and
             Path(plan['code']).name=='repaired.sass', 'repaired plan differs')
        intervals.append((manifest['started_at'],manifest['completed_at']))
        need(data['device']=='NVIDIA GeForce GTX 880M' and data['registry_id']==4294968416 and
             data['GPU_dispatch'] and data['passed'] and data['mismatches']==data['guard_mismatches']==0 and
             data['local']==local and data['groups']==3 and data['variant']==variant and len(data['runs'])==3,
             'GPU identity or dispatch differs: '+name)
        proof=data['import'];native=proof['native_import']
        need(proof['gate_accepted'] and proof['immutable_library_data'] and proof['constructor_restored'] and
             native['contract_verified'] and native['constructor_restored'] and
             native['target_imports']==native['verified_imports']==1 and len(native['events'])==1,
             'SDK gate/import mismatch: '+name)
        event=native['events'][0]
        need(event['expected_original_code_identical'] and event['native_metadata_identical_to_certificate'] and
             event['imported_code_identical'] and event['native_metadata_preserved_except_instruction_count'] and
             event['code_input_unchanged_after_constructor'], 'native payload mismatch: '+name)
        output_hashes=[];slots=set()
        for iteration,row in enumerate(data['runs']):
            seed=0x1234+37*iteration;n=local*3
            need(row['seed']==seed and row['elements']==n and row['compute']['status']==4 and
                 row['readback']['status']==4 and not row['mismatches'] and not row['guard_mismatches'],
                 'execution receipt mismatch: '+name)
            path=directory/'outputs'/('output-%d.bin'%iteration);raw=path.read_bytes()
            need(len(raw)==n*16+128 and raw[:64]==raw[-64:]==b'\xa5'*64,'guards: '+name)
            values=struct.unpack('<%dI'%(n*4),raw[64:-64]);winners=[0,0,0]
            for i in range(n):
                old,success,final,index=values[i*4:i*4+4];group=i//local
                initial=(seed+group*0x10001)&0xffffffff;replacement=seed^0x55667788
                slots.add((seed+group)&3);winners[group]+=success
                noise=((seed*0x9e3779b9)&0xffffffff)^(i*17)
                need(success in (0,1) and old==(initial if variant or success else replacement) and
                     final==(initial if variant else replacement) and index==(i^noise),
                     'raw result differs: '+name)
                operations+=1;words+=4
            need(winners==([0,0,0] if variant else [1,1,1]), 'winner count differs: '+name)
            output_hashes.append(sha(path))
        need(slots=={0,1,2,3},'source slot coverage differs')
        receipts.append({'name':name,'operations':local*9,'output_SHA256':output_hashes,
                         'signed_executable_SHA256':manifest['signed_binary_sha256'],
                         'certificate_template_SHA256':manifest.get('certificate_template_SHA256')})
    template=json.loads((work/'certificate.json').read_text())
    wrong_profile=json.loads((work/'bad-profile.json').read_text())
    expected_profile=dict(template);expected_profile['repair_profile']='unqualified-other'
    need(wrong_profile==expected_profile, 'wrong-profile control changed additional fields')
    wrong_metadata=json.loads((work/'bad-metadata.json').read_text())
    original_metadata=base64.b64decode(template['native_metadata_base64'])
    changed_metadata=bytearray(original_metadata);changed_metadata[100]^=1
    expected_metadata=dict(template)
    expected_metadata['native_metadata_base64']=base64.b64encode(changed_metadata).decode()
    expected_metadata['native_metadata_SHA256']=hashlib.sha256(changed_metadata).hexdigest()
    need(wrong_metadata==expected_metadata, 'wrong-metadata control changed additional fields')
    original=(work/'original.sass').read_bytes();wrong=(work/'wrong-original.sass').read_bytes()
    repaired=(work/'repaired.sass').read_bytes();trampoline=(work/'trampoline.sass').read_bytes()
    need(len(wrong)==len(original) and [i for i in range(len(original)) if wrong[i]!=original[i]]==[0] and
         len(repaired)==len(trampoline) and
         [i for i in range(0,len(repaired),8) if repaired[i:i+8]!=trampoline[i:i+8]]==[0x5d0],
         'code negative controls differ')
    templates={'negative-pin-v1-l33-2':'certificate.json','negative-trampoline':'certificate.json',
               'negative-profile':'bad-profile.json','negative-metadata':'bad-metadata.json'}
    refusals=[]
    for name in negative:
        directory=work/name;manifest=json.loads((directory/'manifest.json').read_text())
        data=json.loads((directory/'execution.stdout').read_text())
        plan=json.loads((directory/'plan.json').read_text())
        check_host(directory,manifest,build,4);intervals.append((manifest['started_at'],manifest['completed_at']))
        need(manifest['certificate_template_SHA256']==sha(work/templates[name]), 'negative template differs: '+name)
        need(Path(plan['original_code']).name==('wrong-original.sass' if name=='negative-pin-v1-l33-2' else 'original.sass') and
             Path(plan['code']).name==('trampoline.sass' if name=='negative-trampoline' else 'repaired.sass'),
             'negative program selection differs: '+name)
        need(data['failure_stage']=='pipeline' and not data.get('GPU_dispatch') and
             not data['import']['gate_accepted'] and not data['import']['constructor_entered'],
             'refusal did not precede constructor: '+name)
        refusals.append({'name':name,'before_constructor':True,
                         'certificate_template_SHA256':manifest.get('certificate_template_SHA256')})
    intervals.sort();need(all(s<=e for s,e in intervals) and
        all(intervals[i][1]<=intervals[i+1][0] for i in range(len(intervals)-1)), 'overlapping hosts')
    report={'status':'PASS','GPU_correct_operations':operations,'GPU_checked_words':words,
            'GPU_hosts':len(tests),'pre_constructor_refusals':refusals,
            'terminal_nonoverlapping_processes':len(intervals),'adapter_SHA256':build['adapter_SHA256'],
            'client_SHA256':build['probe_SHA256'],'certificate_template_SHA256':build['certificate_SHA256'],
            'receipts':receipts,'general_shader_support':False,'code_residency_readback':False,
            'performance_benchmark':False}
    with out.open('x') as stream:json.dump(report,stream,indent=2,sort_keys=True);stream.write('\n')
    print(json.dumps(report,indent=2))


def check_host(directory,manifest,build,exit_code):
    need(manifest['exit_code']==exit_code and not manifest['SIGKILL_requested'] and
         not manifest['authoritative_ps_status'] and manifest['GPU_reservation']['state']=='terminal' and
         manifest['original_binary_sha256']==build['probe_SHA256'] and
         manifest['signed_binary_sha256']==sha(directory/'application'), 'host state or identity differs')
    result=subprocess.run(['codesign','--verify','--strict',str(directory/'application')],
                          capture_output=True,timeout=15)
    need(result.returncode==0,'signed host verification failed')


if __name__=='__main__':main()
