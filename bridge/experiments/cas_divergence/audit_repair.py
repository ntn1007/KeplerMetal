#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck exact conditional-CAS repair, controls and raw GPU readbacks."""
import argparse
import hashlib
import json
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

EXPERIMENT=Path(__file__).resolve().parent
BRIDGE=EXPERIMENT.parents[1]
sys.path.insert(0,str(BRIDGE/'tools'))
from recognize_native_cas import verify_decoder
from run_repair import SYSTEM


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def need(value,message):
    if not value:raise ValueError(message)


def verify_outputs(directory):
    with tempfile.TemporaryDirectory(prefix='kepler-divergence-repair-audit-') as temporary:
        dest=Path(temporary)/'verified.json'
        r=subprocess.run([sys.executable,str(EXPERIMENT/'verify.py'),'--report',str(directory/'report.json'),
                          '--outputs',str(directory/'outputs'),'--out',str(dest)],capture_output=True,timeout=90)
        need(r.returncode==0,'independent numerical oracle failed')
        result=json.loads(dest.read_text());need(result==json.loads((directory/'verified.json').read_text()),
                                                'saved oracle differs from raw outputs')
        return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('build','decoder','reference','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--runs',type=Path,nargs=7,required=True)
    a=p.parse_args();build=a.build.resolve();out=a.out.resolve()
    need(not out.exists() and out.parent.is_dir(),'fresh output required')
    need(sha(build/'repair_host.mm')==sha(EXPERIMENT/'repair_host.mm') and
         sha(build/'import.mm')==sha(BRIDGE/'src/KeplerNativeCAS.mm'),'host source differs')
    original=(build/'original.sass').read_bytes();repaired=(build/'repaired.sass').read_bytes()
    trampoline=(build/'trampoline.sass').read_bytes();wrong=(build/'wrong-original.sass').read_bytes()
    need(len(original)==0x540 and len(repaired)==len(trampoline)==0x580 and
         sha(build/'original.sass')=='83fedb1873bf54ae9975d3f44bd8e8512a9639903afee18d2decef4fbcdd2eb2' and
         sha(build/'shader.metallib')=='811e53236f858247d59ae1540efb1a74160c0e566522faadd9fa82ad60de8640',
         'original profile differs')
    need([i for i in range(0,len(original),8) if original[i:i+8]!=repaired[i:i+8]]==[0x428] and
         [i for i in range(0,len(repaired),8) if repaired[i:i+8]!=trampoline[i:i+8]]==[0x550] and
         len(wrong)==len(original) and [i for i in range(len(original)) if original[i]!=wrong[i]]==[0],
         'control construction differs')
    need(repaired[0x548:0x550]==original[0x428:0x430] and
         struct.unpack_from('<Q',repaired,0x550)[0]==0x2800000000011de4 and
         struct.unpack_from('<Q',trampoline,0x550)[0]==0x4000000000001de4,
         'displaced or corrective instruction differs')
    listing=(build/'repaired.asm').read_text();need(verify_decoder(repaired,listing,a.decoder),'decoder replay failed')
    for offset,op in [(0x428,'bra 0x548'),(0x548,'mov b32 $r10 0x80000000'),
                      (0x550,'mov b32 $r4 $r0'),(0x558,'bra 0x430')]:
        need(any(line.startswith('%08x:'%offset) and line.endswith(op) for line in listing.splitlines()),
             'decoded branch or stub differs')
    build_manifest=build/'build.json'
    if build_manifest.exists():
        frozen=json.loads(build_manifest.read_text())['files_SHA256']
        for name,digest in frozen.items():need(sha(build/name)==digest,'build snapshot changed: '+name)
        need(sha(build/'src/KeplerNativeCASAdapter.inc')==sha(BRIDGE/'src/KeplerNativeCASAdapter.inc'),
             'compiled adapter snapshot differs')
    modes=('negative-pin','native','replay','trampoline','trampoline','repaired','repaired')
    intervals=[];receipts=[]
    for mode,directory in zip(modes,a.runs):
        directory=directory.resolve();manifest=json.loads((directory/'manifest.json').read_text())
        report=json.loads((directory/'report.json').read_text())
        need(manifest['GPU_reservation']['state']=='terminal' and not manifest['SIGKILL_requested'] and
             not manifest['authoritative_ps_status'] and manifest['exit_code']==(4 if mode=='negative-pin' else 0) and
             report['mode']==mode,'host lifecycle or mode differs')
        need(manifest['original_binary_sha256']==sha(build/'host') and
             manifest['signed_binary_sha256']==sha(directory/'application') and
             manifest['source_SHA256']['repair_host.mm']==sha(build/'repair_host.mm') and
             manifest['source_SHA256']['import.mm']==sha(build/'import.mm') and
             manifest['code_SHA256']['shader.metallib']==sha(build/'shader.metallib')==sha(directory/'shader.metallib'),
             'host or input identity differs')
        arguments=manifest['arguments']
        expected_original='wrong-original.sass' if mode=='negative-pin' else 'original.sass'
        expected_replacement={'negative-pin':'repaired.sass','native':'original.sass','replay':'original.sass',
                              'trampoline':'trampoline.sass','repaired':'repaired.sass'}[mode]
        need(len(arguments)==5 and Path(arguments[0]).name=='shader.metallib' and
             Path(arguments[1]).name=='outputs' and arguments[2]==mode and
             Path(arguments[3]).name==expected_original and Path(arguments[4]).name==expected_replacement,
             'program-selection arguments differ')
        sign=subprocess.run(['codesign','--verify','--strict',str(directory/'application')],capture_output=True,timeout=15)
        need(sign.returncode==0,'signature verification failed')
        if 'system_before' in manifest:
            need(manifest['system_before']==manifest['system_after']==SYSTEM and
                 manifest['build_manifest_SHA256']==sha(build_manifest),'system or build snapshot differs')
        intervals.append((manifest['started_at'],manifest['completed_at']))
        proof=report.get('import',{})
        if mode=='negative-pin':
            need(not report['GPU_dispatch'] and report['failure_stage']=='pipeline' and
                 not proof['contract_verified'] and proof['constructor_restored'] and
                 any(event.get('expected_original_code_identical') is False for event in proof['events']) and
                 not any((directory/'outputs').iterdir()),
                 'wrong pin was not refused before dispatch')
            receipts.append({'mode':mode,'before_GPU_dispatch_refused':True,
                             'signed_host_SHA256':manifest['signed_binary_sha256']})
            continue
        need(report['GPU_dispatch'] and report['device']=='NVIDIA GeForce GTX 880M' and
             report['registry_id']==4294968416 and len(report['runs'])==48,'GPU identity or dispatch differs')
        if mode!='native':
            need(proof['contract_verified'] and proof['constructor_restored'] and
                 proof['target_imports']==proof['verified_imports']==1 and
                 proof['driver_sha256']=='e240d54a4cd64b7e54fbc15250de82e88451132e1d9f3a4f9879607c8b0e7645',
                 'native import not verified')
            for event in proof['events']:
                need(event['expected_original_code_identical'] and event['imported_code_identical'] and
                     event['native_metadata_preserved_except_instruction_count'] and event['code_input_unchanged_after_constructor'],
                     'native payload or metadata mismatch')
        verified=verify_outputs(directory);expected=0 if mode=='repaired' else 14226
        need(verified['checked_words']==227520 and verified['dispatches']==48 and
             verified['totals']=={'active_expected':expected,'inactive_expected':0,'success':0,
                                  'final':0,'witness':0,'guard_bytes':0}, 'numerical result differs')
        for case in verified['cases']:
            wrong_active=0 if mode=='repaired' or case['variant']==0 else case['expected_active']
            need(case['mismatches']['active_expected']==wrong_active,'per-pattern mismatch differs')
        receipts.append({'mode':mode,'dispatches':verified['dispatches'],'checked_words':verified['checked_words'],
                         'active_CAS_operations':sum(x['expected_active'] for x in verified['cases']),
                         'totals':verified['totals'],'signed_host_SHA256':manifest['signed_binary_sha256'],
                         'raw_output_SHA256':[x['output_SHA256'] for x in verified['cases']]})
    intervals.sort();need(all(start<=end for start,end in intervals) and
        all(intervals[i][1]<=intervals[i+1][0] for i in range(len(intervals)-1)),'overlapping host processes')
    reference_path=a.reference.resolve()
    need(sha(reference_path/'report.json')=='7826ecd3bc6dd757f559186660ae8f12d4fb1127aa1fdf2354d562f07a4483df' and
         sha(reference_path/'verified.json')=='8bc3dc0aa1732ec16120eb876f6163ff1871b783cc6b5d3c7c5779b6468a316f',
         'M1 reference snapshot differs')
    reference=verify_outputs(reference_path)
    need(reference['device']=='Apple M1 Max' and reference['status']=='PASS' and reference['checked_words']==227520,
         'M1 reference differs')
    result={'status':'PASS','source_program_SHA256':sha(build/'original.sass'),
            'repaired_program_SHA256':sha(build/'repaired.sass'),'control_program_SHA256':sha(build/'trampoline.sass'),
            'client_SHA256':sha(build/'host'),'decoder_SHA256':sha(a.decoder),
            'build_snapshot_recorded':build_manifest.exists(),'terminal_nonoverlapping_processes':len(intervals),
            'receipts':receipts,'M1_reference_checked_words':reference['checked_words'],
            'resident_instruction_readback':False,'automatic_shader_recognition':False,
            'system_driver_modified':False,'performance_benchmark':False}
    with out.open('x') as stream:json.dump(result,stream,indent=2,sort_keys=True);stream.write('\n')
    print(json.dumps({'status':'PASS','terminal_processes':len(intervals),
                      'repaired_active_CAS_operations':sum(x.get('active_CAS_operations',0) for x in receipts if x['mode']=='repaired'),
                      'm1_reference':reference['status']}))


if __name__=='__main__':main()
