#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck the conditional-CAS SDK profile, gate refusals and GPU outputs."""
import argparse
import base64
import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

EXPERIMENT=Path(__file__).resolve().parent
BRIDGE=EXPERIMENT.parents[1]
sys.path.insert(0,str(BRIDGE/'tools'))
from recognize_native_cas import verify_decoder
from audit_repair import verify_outputs
from run_repair import PINS,SYSTEM


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def need(value,message):
    if not value:raise ValueError(message)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('build','decoder','reference','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--runs',nargs=8,type=Path,required=True)
    a=p.parse_args();build=a.build.resolve();out=a.out.resolve()
    need(not out.exists() and out.parent.is_dir(),'fresh output required')
    base=json.loads((build/'build.json').read_text());sdk=json.loads((build/'sdk-build.json').read_text())
    for name,digest in base['files_SHA256'].items():need(sha(build/name)==digest,'base build changed: '+name)
    for name,key in [('host-sdk','host_SHA256'),('sdk_host.mm','host_source_SHA256'),
                     ('sdk_wrapper.mm','wrapper_SHA256'),('src/KeplerNativeCASAdapter.inc','adapter_SHA256'),
                     ('certificate.json','certificate_SHA256')]:need(sha(build/name)==sdk[key],'SDK build changed: '+name)
    need(sha(build/'src/KeplerNativeCASAdapter.inc')==sha(BRIDGE/'src/KeplerNativeCASAdapter.inc') and
         sha(build/'sdk_wrapper.mm')==sha(EXPERIMENT/'sdk_wrapper.mm'),'public source differs')
    for name,digest in PINS.items():need(sha(build/name)==digest,'code pin differs: '+name)
    original=(build/'original.sass').read_bytes();repaired=(build/'repaired.sass').read_bytes()
    trampoline=(build/'trampoline.sass').read_bytes()
    need([i for i in range(0,len(original),8) if original[i:i+8]!=repaired[i:i+8]]==[0x428] and
         [i for i in range(0,len(repaired),8) if repaired[i:i+8]!=trampoline[i:i+8]]==[0x550] and
         repaired[0x548:0x550]==original[0x428:0x430] and
         verify_decoder(repaired,(build/'repaired.asm').read_text(),a.decoder),'repair structure differs')
    template=json.loads((build/'certificate.json').read_text())
    need(template['repair_profile']=='gk104-conditional-pinned-v1' and
         template['qualification']=='manual-exact-profile-gpu-tested' and
         template['AIR']['qualified'] is False and template['SASS']['qualified'] is False and
         template['AIR']['reason']=='Expected is not directly inserted into one output vector' and
         template['SASS']['reason']=='indirect or unsupported branch' and
         hashlib.sha256(base64.b64decode(template['native_metadata_base64'])).hexdigest()==
             'f99b8ca94aec90088ba8aee80c42b9e242a7829a81c3fedbf34b2312b08bacbe',
         'certificate misrepresents diagnosis or metadata')
    modes=('negative-pin','negative-nop','negative-profile','negative-metadata','negative-air','native','repaired','repaired')
    intervals=[];receipts=[]
    for mode,directory in zip(modes,a.runs):
        directory=directory.resolve();manifest=json.loads((directory/'manifest.json').read_text())
        report=json.loads((directory/'report.json').read_text());negative=mode.startswith('negative-')
        host_mode={'negative-nop':'trampoline','negative-profile':'repaired',
                   'negative-metadata':'repaired','negative-air':'repaired'}.get(mode,mode)
        need(manifest['test_mode']==mode and report['mode']==host_mode and
             manifest['GPU_reservation']['state']=='terminal' and manifest['exit_code']==(4 if negative else 0) and
             not manifest['SIGKILL_requested'] and not manifest['authoritative_ps_status'] and
             manifest['system_before']==manifest['system_after']==SYSTEM and
             manifest['SDK_build_SHA256']==sha(build/'sdk-build.json') and
             manifest['original_binary_sha256']==sdk['host_SHA256'] and
             manifest['signed_binary_sha256']==sha(directory/'application') and
             sha(directory/'shader.metallib')==PINS['shader.metallib'],'process or input differs: '+mode)
        signature=subprocess.run(['codesign','--verify','--strict',str(directory/'application')],capture_output=True,timeout=15)
        need(signature.returncode==0,'signed host differs')
        cert=json.loads((directory/'certificate.json').read_text());expected=copy.deepcopy(template)
        if mode=='negative-profile':expected['repair_profile']='unqualified-other'
        if mode=='negative-air':expected['AIR']['qualified']=True
        if mode=='negative-metadata':
            metadata=bytearray(base64.b64decode(expected['native_metadata_base64']));metadata[100]^=1
            expected['native_metadata_base64']=base64.b64encode(metadata).decode()
            expected['native_metadata_SHA256']=hashlib.sha256(metadata).hexdigest()
        need(cert==expected and sha(directory/'certificate.json')==manifest['certificate_template_SHA256'],
             'certificate control differs: '+mode)
        args=manifest['arguments'];original='wrong-original.sass' if mode=='negative-pin' else 'original.sass'
        replacement='trampoline.sass' if mode=='negative-nop' else 'original.sass' if mode=='native' else 'repaired.sass'
        need(len(args)==5 and args[2]==host_mode and Path(args[3]).name==original and Path(args[4]).name==replacement,
             'program selection differs: '+mode)
        intervals.append((manifest['started_at'],manifest['completed_at']))
        proof=report['import']
        if negative:
            need(not report['GPU_dispatch'] and report['failure_stage']=='pipeline' and
                 not proof['gate_accepted'] and not proof['constructor_entered'] and not any((directory/'outputs').iterdir()),
                 'negative was not refused before constructor: '+mode)
            receipts.append({'mode':mode,'before_constructor_refused':True,'signed_host_SHA256':manifest['signed_binary_sha256']})
            continue
        need(report['GPU_dispatch'] and report['device']=='NVIDIA GeForce GTX 880M' and
             report['registry_id']==4294968416 and len(report['runs'])==48,'GPU identity differs')
        if mode=='repaired':
            need(proof['gate_accepted'] and proof['immutable_library_data'] and proof['constructor_restored'],
                 'SDK gate not verified')
            native=proof['native_import']
            need(native['contract_verified'] and native['constructor_restored'] and
                 native['target_imports']==native['verified_imports']==1 and len(native['events'])==1,
                 'native import not verified')
            event=native['events'][0]
            need(event['native_metadata_identical_to_certificate'] and event['expected_original_code_identical'] and
                 event['imported_code_identical'] and event['native_metadata_preserved_except_instruction_count'] and
                 event['code_input_unchanged_after_constructor'],'native code or metadata differs')
        verified=verify_outputs(directory);wrong=0 if mode=='repaired' else 14226
        need(verified['checked_words']==227520 and verified['dispatches']==48 and
             verified['totals']=={'active_expected':wrong,'inactive_expected':0,'success':0,'final':0,'witness':0,'guard_bytes':0},
             'raw numerical outcome differs')
        for row in verified['cases']:
            need(row['mismatches']['active_expected']==(row['expected_active'] if mode=='native' and row['variant']==1 else 0),
                 'per-pattern mismatch differs')
        receipts.append({'mode':mode,'dispatches':verified['dispatches'],'checked_words':verified['checked_words'],
                         'active_CAS_operations':sum(x['expected_active'] for x in verified['cases']),
                         'totals':verified['totals'],'signed_host_SHA256':manifest['signed_binary_sha256'],
                         'raw_output_SHA256':[x['output_SHA256'] for x in verified['cases']]})
    intervals.sort();need(all(s<=e for s,e in intervals) and
        all(intervals[i][1]<=intervals[i+1][0] for i in range(len(intervals)-1)),'hosts overlap')
    reference=a.reference.resolve()
    need(sha(reference/'report.json')=='7826ecd3bc6dd757f559186660ae8f12d4fb1127aa1fdf2354d562f07a4483df' and
         sha(reference/'verified.json')=='8bc3dc0aa1732ec16120eb876f6163ff1871b783cc6b5d3c7c5779b6468a316f',
         'M1 reference snapshot differs')
    ref=verify_outputs(reference);need(ref['status']=='PASS' and ref['device']=='Apple M1 Max','M1 oracle differs')
    result={'status':'PASS','adapter_SHA256':sdk['adapter_SHA256'],'host_SHA256':sdk['host_SHA256'],
            'manual_exact_profile':True,'AIR_and_flow_recognizers_qualified':False,
            'terminal_nonoverlapping_processes':len(intervals),'receipts':receipts,
            'M1_reference_checked_words':ref['checked_words'],'resident_instruction_readback':False,
            'transparent_application_support':False,'performance_benchmark':False}
    with out.open('x') as stream:json.dump(result,stream,indent=2,sort_keys=True);stream.write('\n')
    print(json.dumps({'status':'PASS','processes':len(intervals),
        'correct_active_CAS_operations':sum(x.get('active_CAS_operations',0) for x in receipts if x['mode']=='repaired')}))


if __name__=='__main__':main()
