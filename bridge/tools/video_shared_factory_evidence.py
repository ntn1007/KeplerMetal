#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check an offline, pinned REA capture of the NVIDIA type-6 factory."""
import argparse
import json
from pathlib import Path
from compare_video_profile import symbols_and_external_relocations
from video_method_contract import GE_SHA, sha, symbol_one
from video_resource_ownership import check_evidence

SPEC = ('factory', '86cd77050160acc767cfeb929049fa756e03ac6011d0db01663b3d7bfe69500b',
        'ev_62c777b2ac1ff72567dfa7053a53d60ae457e30c16d5e3a277eb90c80d3e3959', 1045,
        ['0xd3ca: CMP ECX, 0x6', '0xd54a: CALL 0x0000d73e',
         '0xd55e: CALL 0x0000d73e', '0xd577: CALL 0x0000d73e',
         '0xd6d4: MOV R13D, 0xe00002c9'])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--geforce',type=Path,required=True)
    p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    if a.out.exists() or not a.out.parent.is_dir():
        raise ValueError('Fresh output file required')
    b=a.geforce.read_bytes()
    if sha(b)!=GE_SHA:
        raise ValueError('Pinned GeForce profile differs')
    symbols,_=symbols_and_external_relocations(b)
    if (symbol_one(symbols,'__ZN13nvAccelerator13newUserClientEP4taskPvjPP12IOUserClient')['value'] != 0xd328 or
        symbol_one(symbols,'__ZN13nvAccelerator17FindDeviceForTaskEP4taskj')['value'] != 0xd73e):
        raise ValueError('Factory symbols changed')
    capture=check_evidence(a.capture,'0xd328',SPEC,subject_sha=GE_SHA)
    out={'status':'PASS','GeForce_SHA256':GE_SHA,'factory':capture,
         'type6_static_task_device_lookup':True,'lookup_target':'0xd73e',
         'missing_device_path_error':'0xe00002c9',
         'actual_runtime_branch_observed':False,'runtime_refusal_cause_proved':False}
    with a.out.open('x') as f:
        json.dump(out,f,indent=2);f.write('\n')
    print(json.dumps({'status':out['status'],'runtime_refusal_cause_proved':False}))

if __name__=='__main__':
    main()
