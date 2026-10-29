#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check a bounded historical AppleGVA selection branch without executing it."""
import argparse
import importlib.util
import json
from pathlib import Path

_source = Path(__file__).resolve().parent.parent / 'video_gva_historical_classification' / 'audit.py'
_spec = importlib.util.spec_from_file_location('historical_classification_audit', _source)
_historical = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_historical)
OLD_SHA, REA_SHA = _historical.OLD_SHA, _historical.REA_SHA
digest, macho_profile, need = _historical.digest, _historical.macho_profile, _historical.need

FUNCTION_SHA = '663c2667a023594584d8adad46535c9431dbd4ebfa1e30835a80ffecc5b1a5ae'
EVIDENCE = 'ev_931bf92d58c7106a382a89793c44f1a449547dd15df2b697589287a5b3134103'


def verify(legacy, bundle):
    need(digest(legacy) == OLD_SHA, 'historical image differs')
    macho_profile(legacy)
    need(digest(legacy[0x23e22:0x24afd]) == FUNCTION_SHA, 'function body differs')
    need(digest(bundle) == REA_SHA, 'retained analysis differs')
    records = json.loads(bundle)['records']
    rows = [r for r in records if r.get('evidence_id') == EVIDENCE]
    need(len(rows) == 1 and rows[0]['subject']['digest']['sha256'] == OLD_SHA,
         'analysis identity differs')
    record = rows[0]['normalized_result']
    need(record['procedure']['address'] == '0x23e22' and
         record['procedure']['body']['ranges'] == [{'start': '0x23e22', 'end': '0x24afc'}],
         'analysis function boundary differs')
    assembly = record['assembly']
    required = (
        '0x24163: CMP R10D, 0x1040008', '0x2416a: JNZ 0x000241d1',
        '0x2416c: INC R9D',
        '0x2416f: MOV R15, RBX', '0x2423f: CMP R9D, 0x1',
        '0x24243: JNZ 0x0002432e', '0x24302: OR R15, qword ptr [RBP + -0x128]',
        '0x24309: JZ 0x000243c0', '0x2430f: CMP dword ptr [RBP + -0xc8], 0x5',
        '0x24316: JZ 0x0002404a', '0x2431c: CMP dword ptr [RBP + -0xc8], 0x9',
        '0x24323: JZ 0x0002404a', '0x243c0: MOV R13, qword ptr [RBP + -0xb8]',
        '0x243c7: TEST R13, R13', '0x243ca: JNZ 0x0002440e',
        '0x2441d: JZ 0x0002457e', '0x24423: MOV qword ptr [RCX], R13',
        '0x2442b: ADD qword ptr [RDI + 0x8], RAX',
        '0x24218: CMP byte ptr [RBX + 0x441], 0x0',
        '0x24221: CMP byte ptr [RBX + 0x442], 0x0')
    need(all(x in assembly for x in required), 'required static instructions missing')
    return {
        'status': 'PASS_PINNED_STATIC_BRANCH', 'historical_sha256': OLD_SHA,
        'function_sha256': FUNCTION_SHA, 'rea_bundle_sha256': REA_SHA,
        'evidence_id': EVIDENCE, 'candidate_value': '0x01040008',
        'condition': 'one counted candidate and nonzero NVIDIA-class candidate',
        'excluded_request_values_on_that_branch': [5, 9],
        'request_value_semantics_proved': False, 'selection_always_proved': False,
        'current_runtime_cause_proved': False, 'hardware_video_execution_proved': False,
        'vendor_code_executed': False, 'system_modified': False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('legacy', 'rea', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    need(not args.out.exists() and args.out.parent.is_dir(), 'fresh output required')
    receipt = verify(args.legacy.read_bytes(), args.rea.read_bytes())
    with args.out.open('x') as handle:
        json.dump(receipt, handle, sort_keys=True, indent=2)
        handle.write('\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
