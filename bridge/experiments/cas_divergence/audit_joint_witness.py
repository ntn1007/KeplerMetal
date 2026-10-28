#!/usr/bin/env python3
"""Audit two joint-witness cohorts and compare archived per-thread observations."""
import argparse
import hashlib
import json
import struct
import subprocess
import sys
from pathlib import Path
from run_repair import PINS, SYSTEM
from verify_joint_witness import compare

HERE = Path(__file__).resolve().parent
BRIDGE = HERE.parents[1]
sys.path.insert(0, str(BRIDGE / 'tools'))
from recognize_native_cas import verify_decoder

TRACE = '48997eb3c66a0a40e6f6d72bbb5b4ada4f6cc7fd7d4f1047a3c6efccbe241427'
METADATA = 'f99b8ca94aec90088ba8aee80c42b9e242a7829a81c3fedbf34b2312b08bacbe'

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def need(condition, reason):
    if not condition:
        raise ValueError(reason)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name, count in (('builds', 2), ('baselines', 8), ('runs', 8), ('branch-runs', 8), ('target-runs', 8)):
        p.add_argument('--' + name, nargs=count, type=Path, required=True)
    for name in ('decoder', 'original-listing', 'branch-audit', 'target-audit', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    need(not a.out.exists() and a.out.parent.is_dir(), 'fresh output required')
    decoder = a.decoder
    hosts = set()
    for build in a.builds:
        m = json.loads((build / 'build.json').read_text())
        need(m['GPU_dispatch'] is False and m['system'] == SYSTEM, 'build context differs')
        for name, digest in m['files_SHA256'].items():
            need(sha(build / name) == digest, 'build differs: ' + name)
        need(sha(build / 'trace.sass') == TRACE and sha(build / 'original.sass') == PINS['original.sass'] and
             sha(build / 'shader.metallib') == PINS['shader.metallib'] and sha(build / 'native.metadata') == METADATA and
             sha(build / 'KeplerNativeCAS.mm') == sha(BRIDGE / 'src/KeplerNativeCAS.mm') and
             sha(build / 'src/KeplerConditionalAux.h') == sha(BRIDGE / 'src/KeplerConditionalAux.h') and
             sha(build / 'src/KeplerNativeCASAdapter.inc') == sha(BRIDGE / 'src/KeplerNativeCASAdapter.inc'), 'build profile differs')
        for name in ('branch_witness_host.mm', 'cb0_readback_import.mm'):
            need(sha(build / name) == sha(HERE / name), 'host source differs')
        old, new = (build / 'original.sass').read_bytes(), (build / 'trace.sass').read_bytes()
        need(len(new) == len(old) + 192 and [j for j in range(0, len(old), 8) if old[j:j+8] != new[j:j+8]] == [0x290, 0x330, 0x528] and
             new[0x5a0:0x5a8] == old[0x330:0x338] and new[0x5d0:0x5d8] == old[0x528:0x530] and
             verify_decoder(old, a.original_listing.read_text(), decoder) and
             verify_decoder(new, (build / 'trace.asm').read_text(), decoder), 'code or decoder differs')
        hosts.add(sha(build / 'host'))
    need(len(hosts) == 1, 'hosts differ')
    branch_audit = json.loads(a.branch_audit.read_text())
    target_audit = json.loads(a.target_audit.read_text())
    need(branch_audit['status'] == target_audit['status'] == 'PASS', 'prior audit failed')
    def read(root, mode, pattern, build=None):
        m = json.loads((root / 'manifest.json').read_text())
        report = json.loads((root / 'report.json').read_text())
        args = m['arguments']
        need(m['mode'] == mode and m['pattern'] == pattern and m['exit_code'] == 0 and
             m['GPU_reservation']['state'] == 'terminal' and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and
             m['system_before'] == m['system_after'] == SYSTEM and m['original_binary_sha256'] in hosts and
             m['signed_binary_sha256'] == sha(root / 'application') and
             (build is None or m['build_sha256'] == sha(build / 'build.json')), 'process evidence differs')
        need(len(args) == 7 and args[1] == mode and args[6] == str(pattern) and sha(args[2]) == PINS['shader.metallib'] and
             sha(args[3]) == METADATA and sha(args[4]) == PINS['original.sass'] and
             sha(args[5]) == (PINS['original.sass'] if mode == 'baseline' else TRACE), 'process input differs')
        need(subprocess.run(['codesign', '--verify', '--strict', str(root / 'application')], capture_output=True, timeout=15).returncode == 0, 'signature differs')
        proof = report['import']
        events = proof['events']
        need(proof['contract_verified'] and proof['constructor_restored'] and len(events) == 1 and
             all(events[0][key] for key in ('conditional_auxiliary_section_pinned', 'expected_original_code_identical',
                 'native_metadata_identical_to_certificate', 'imported_code_identical',
                 'native_metadata_preserved_except_instruction_count', 'code_input_unchanged_after_constructor')), 'constructor evidence differs')
        return (root / 'output.bin').read_bytes(), report, (m['started_at'], m['completed_at'])
    receipts, intervals = [], []
    for cohort in range(2):
        for i, pattern in enumerate((0, 2, 3, 4)):
            index = cohort * 4 + i
            baseline, br, _ = read(a.baselines[index], 'baseline', pattern)
            trace, tr, interval = read(a.runs[index], 'trace', pattern, a.builds[cohort])
            result = compare(baseline, br, trace, tr)
            candidates = [r for r in branch_audit['receipts'] if r['cohort'] == cohort + 1 and r['pattern'] == pattern]
            targets = [r for r in target_audit['receipts'] if r['cohort'] == cohort + 1 and r['pattern'] == pattern and r['target'] == '0x330']
            need(len(candidates) == len(targets) == 1, 'prior receipt missing or duplicated')
            branch_raw = (a.branch_runs[index] / 'output.bin').read_bytes()
            target_raw = (a.target_runs[index] / 'output.bin').read_bytes()
            need(hashlib.sha256(baseline).hexdigest() == candidates[0]['baseline_sha256'] == targets[0]['baseline_sha256'] and
                 hashlib.sha256(branch_raw).hexdigest() == candidates[0]['trace_sha256'] and
                 hashlib.sha256(target_raw).hexdigest() == targets[0]['trace_sha256'], 'prior result digest differs')
            mismatches = 0
            for thread in range(99):
                offset = 68 + thread * 16
                branch, target, joint = (struct.unpack_from('<I', raw, offset)[0] for raw in (branch_raw, target_raw, trace))
                need(target in (0, 1), 'prior target marker differs')
                if joint != branch + (target == 0):
                    mismatches += 1
            need(mismatches == 0, 'combined markers do not match prior per-thread witnesses')
            intervals.append(interval)
            receipts.append({'cohort': cohort + 1, **result, 'prior_per_thread_mismatches': mismatches})
    intervals.sort()
    need(all(start <= end for start, end in intervals) and all(intervals[i][1] <= intervals[i+1][0] for i in range(len(intervals)-1)), 'GPU trace processes overlap')
    for i in range(4):
        need(receipts[i]['markers'] == receipts[i+4]['markers'], 'cohort marker histograms differ')
    result = {'status': 'PASS', 'cohorts': 2, 'trace_processes': 8, 'rows_per_process': 99,
              'receipts': receipts, 'correlation_same_instrumented_invocation': True,
              'direct_origin_proved': False, 'resident_instructions_read_back': False,
              'all_paths_qualified': False, 'performance_benchmark': False}
    with a.out.open('x') as output:
        json.dump(result, output, indent=2, sort_keys=True)
        output.write('\n')
    print(json.dumps(result))

if __name__ == '__main__':
    main()
