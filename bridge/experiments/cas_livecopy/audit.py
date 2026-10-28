#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck the bounded GTX live-copy CAS experiment from raw readbacks."""
import argparse
import hashlib
import json
import struct
import subprocess
from pathlib import Path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def need(value, message):
    if not value:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    work = args.work.resolve()
    need(not args.out.exists() and args.out.parent.is_dir(), 'fresh audit output required')
    original = (work/'original.sass').read_bytes()
    repaired = (work/'repaired.sass').read_bytes()
    trampoline = (work/'trampoline.sass').read_bytes()
    need(len(original) == 0x5c0 and len(repaired) == len(trampoline) == 0x600,
         'program lengths differ')
    need(hashlib.sha256(original).hexdigest() == 'f16bf16da56d5dc060429f6886d2e1d80eafa0a960f48b7d776a3234fb6bcb41',
         'original native program differs')
    need([i for i in range(0,len(original),8) if original[i:i+8] != repaired[i:i+8]] == [0x530],
         'original program changed outside redirect')
    need([i for i in range(0,len(repaired),8) if repaired[i:i+8] != trampoline[i:i+8]] == [0x5d0],
         'control is not identical except correction')
    need(repaired[0x5c8:0x5d0] == original[0x530:0x538], 'displaced instruction not replayed')
    need(struct.unpack_from('<Q', repaired, 0x5d0)[0] == 0x2800000014001de4 and
         struct.unpack_from('<Q', trampoline, 0x5d0)[0] == 0x4000000000001de4,
         'correction/control instruction differs')
    cases = [('native-v1-l33','native',33,1), ('trampoline-v1-l33','native_trampoline',33,1),
             ('repaired-v1-l33','native_repaired',33,1), ('native-v0-l33','native',33,0),
             ('trampoline-v0-l33','native_trampoline',33,0), ('repaired-v0-l33','native_repaired',33,0),
             ('replay-v1-l33','native_replay',33,1), ('native-v1-l128','native',128,1),
             ('repaired-v1-l128','native_repaired',128,1), ('repaired-v0-l128','native_repaired',128,0),
             ('repaired-v0-l33-repeat','native_repaired',33,0),
             ('repaired-v1-l128-repeat','native_repaired',128,1)]
    records = []; intervals=[]
    for name,mode,local,variant in cases:
        path=work/name
        manifest=json.loads((path/'manifest.json').read_text())
        result=json.loads((path/'execution.stdout').read_text())
        plan=json.loads((path/'plan.json').read_text())
        need(plan['mode']==mode and plan['local']==local and plan['variant']==variant and
             plan['groups']==3 and plan['layout']=='noise', 'unexpected plan: '+name)
        need(manifest['GPU_reservation']['state']=='terminal' and not manifest['SIGKILL_requested'] and
             not manifest['authoritative_ps_status'], 'unresolved host: '+name)
        need(manifest['library_SHA256']=='17cd653eb49ab7749f6013145e71292d51ce467f2a094451e6f1fc9192a31632',
             'library fingerprint differs: '+name)
        intervals.append((manifest['started_at'],manifest['completed_at'],name))
        need(manifest['original_binary_sha256']==sha(work/'probe') and
             manifest['signed_binary_sha256']==sha(path/'application'), 'executable mismatch: '+name)
        signature=subprocess.run(['codesign','--verify','--strict',str(path/'application')],capture_output=True,timeout=15)
        need(signature.returncode==0, 'signature failed: '+name)
        need(result['device']=='NVIDIA GeForce GTX 880M' and result['GPU_dispatch'] and
             result['registry_id']==4294968416 and result['mode']==mode and
             result['local']==local and result['groups']==3 and result['variant']==variant and
             len(result['runs'])==3, 'GPU identity or run geometry differs: '+name)
        if mode != 'native':
            expected_code={'native_replay':'original.sass','native_trampoline':'trampoline.sass',
                           'native_repaired':'repaired.sass'}[mode]
            need(Path(plan['code']).name==expected_code and Path(plan['original_code']).name=='original.sass',
                 'wrong code selection: '+name)
            proof=result['import']; need(proof['contract_verified'] and proof['constructor_restored'] and
                proof['target_imports']==proof['verified_imports']==1, 'native import unverified: '+name)
            ev=proof['events'][0]
            need(ev['expected_original_code_identical'] and ev['imported_code_identical'] and
                 ev['native_metadata_preserved_except_instruction_count'], 'import mismatch: '+name)
        wrong=0; counts=0; checked=0; slots=set(); output_hashes=[]
        for iteration,run in enumerate(result['runs']):
            seed=0x1234+37*iteration; n=local*3
            need(run['seed']==seed and run['elements']==n and run['compute']['status']==4 and
                 run['readback']['status']==4 and run['guard_mismatches']==0, 'run mismatch: '+name)
            file=path/'outputs'/('output-%d.bin'%iteration); raw=file.read_bytes()
            need(len(raw)==n*16+128 and raw[:64]==bytes([0xa5])*64 and
                 raw[-64:]==bytes([0xa5])*64, 'guard or length mismatch: '+name)
            values=struct.unpack('<%dI'%(4*n),raw[64:-64]);successes=[0,0,0]
            for i in range(n):
                expected,swapped,final,index=values[4*i:4*i+4];g=i//local
                initial=(seed+g*0x10001)&0xffffffff; replacement=seed^0x55667788
                slots.add((seed+g)&3); successes[g]+=swapped
                wanted=initial if variant or swapped else replacement
                wrong+=expected!=wanted
                counts+=swapped not in (0,1) or (variant==1 and swapped!=0)
                counts+=final!=(initial if variant else replacement)
                noise=((seed*0x9e3779b9)&0xffffffff)^((i*17)&0xffffffff)
                counts+=index!=(i^noise)
                checked+=4
            need(successes==([0,0,0] if variant else [1,1,1]), 'unexpected winner count: '+name)
            output_hashes.append(sha(file))
        expected_wrong=0 if mode=='native_repaired' else (local*9 if variant else (local-1)*9)
        need(slots=={0,1,2,3} and counts==0 and wrong==expected_wrong and
             result['mismatches']==wrong and result['guard_mismatches']==0 and
             result['passed']==(wrong==0), 'independent numerical mismatch: '+name)
        records.append({'name':name,'mode':mode,'local':local,'variant':variant,
                        'operations':local*9,'checked_words':checked,'wrong_expected_words':wrong,
                        'other_wrong_words':counts,'output_SHA256':output_hashes,
                        'signed_executable_SHA256':manifest['signed_binary_sha256']})
    negative=work/'negative-pin-v1-l33'
    negative_result=json.loads((negative/'execution.stdout').read_text())
    negative_manifest=json.loads((negative/'manifest.json').read_text())
    wrong=(work/'wrong-original.sass').read_bytes()
    need(len(wrong)==len(original) and [i for i in range(len(original)) if wrong[i]!=original[i]]==[0],
         'wrong native pin must differ by one byte')
    need(negative_manifest['GPU_reservation']['state']=='terminal' and
         negative_manifest['exit_code']==4 and not negative_manifest['SIGKILL_requested'] and
         not negative_manifest['authoritative_ps_status'] and
         negative_manifest['signed_binary_sha256']==sha(negative/'application'), 'negative host unresolved')
    intervals.append((negative_manifest['started_at'],negative_manifest['completed_at'],'negative-pin'))
    intervals.sort()
    need(all(start<=end for start,end,_ in intervals) and
         all(intervals[i][1]<=intervals[i+1][0] for i in range(len(intervals)-1)),
         'cohort processes overlap')
    need(negative_result.get('failure_stage')=='pipeline' and not negative_result.get('GPU_dispatch') and
         not negative_result['import']['contract_verified'] and
         all(not event.get('code_replaced') for event in negative_result['import']['events']),
         'wrong-pin control did not stop before dispatch')
    result={'status':'PASS','scope':'one pinned shader, user-process experiment; no general compiler repair',
            'original_SHA256':sha(work/'original.sass'),'repaired_SHA256':sha(work/'repaired.sass'),
            'trampoline_SHA256':sha(work/'trampoline.sass'),'cases':records,
            'records_checked':len(records),'negative_pin_refused_before_dispatch':True,
            'terminal_nonoverlapping_processes':len(intervals),
            'code_residency_readback':False,
            'performance_benchmark':False}
    with args.out.open('x') as out:
        json.dump(result,out,indent=2,sort_keys=True);out.write('\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':
    main()
