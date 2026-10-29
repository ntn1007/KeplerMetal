#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit two bounded archived cache-breakpoint observations, without replay."""
import argparse
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def need(ok, reason):
    if not ok: raise ValueError(reason)


def read(p):
    return json.loads(Path(p).read_text())


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'build', 'calibration', 'reserved-control', 'out'):
        p.add_argument('--' + name, required=True, type=Path)
    p.add_argument('--runs', required=True, type=Path, nargs=2)
    a = p.parse_args()
    need(a.out.parent.is_dir() and not a.out.exists(), 'fresh output required')
    build, cal, control = read(a.build/'build.json'), read(a.calibration/'calibration.json'), read(a.reserved_control/'manifest.json')
    need(build['status'] == 'PREPARED_ONLY' and build['base_inputs_sha256'] == sha(a.base/'inputs.json') and
         build['calibration_sha256'] == sha(a.calibration/'calibration.json') and
         build['reserved_control_sha256'] == sha(a.reserved_control/'manifest.json'), 'build provenance differs')
    for name, digest in build['frozen'].items(): need(sha(a.build/name) == digest, 'build file differs')
    for name in ('marker.S', 'gva_marker.cpp', 'lldb_witness.py', 'lldb_guard.py'):
        need(sha(HERE/name) == sha(a.build/name), 'current source differs')
    for name, digest in cal['source_sha256'].items():
        need(sha(a.calibration/name) == sha(HERE/name) == digest, 'calibration source differs')
    need(cal['status'] == 'PASS_HARDWARE_BREAKPOINT_CPU_CALIBRATION' and cal['all_seven_processes_exit_zero'] and
         control['status'] == 'PASS_RESERVED_DEBUGGER_CPU' and control['reservation']['state'] == 'terminal' and
         control['debugger_and_target_absent_from_process_table'] and
         control['calibration_sha256'] == sha(a.calibration/'calibration.json') and
         control['log_sha256'] == sha(a.reserved_control/'lldb.log'), 'CPU controls differ')
    receipts = []
    for root in a.runs:
        m = read(root/'manifest.json')
        log = (root/'lldb.log').read_text()
        stderr = (root/'stderr.log').read_text()
        report = read(root/'stdout.json')
        need(m['status'] == 'TERMINAL_SCOPED_DEBUGGER' and m['mode'] == 'current' and m['witness'] == 'on' and
             m['target_and_debugger_absent'] and m['target_exit_code'] == m['debugger_exit_code'] == 0 and
             m['reservation']['state'] == 'terminal' and m['reservation']['child_PID'] == m['debugger_pid'] and
             not m['reservation']['SIGKILL_requested'] and not m['reservation']['authoritative_ps_status'] and
             m['build_sha256'] == sha(a.build/'build.json') and m['runner_sha256'] == sha(HERE/'run_gva.py') and
             m['host_sha256'] == sha(root/'application') == build['frozen']['application'] and
             m['lldb_log_sha256'] == sha(root/'lldb.log') and m['stderr_sha256'] == sha(root/'stderr.log') and
             m['stdout_sha256'] == sha(root/'stdout.json'), 'run provenance differs')
        need(m['decoder_status'] == -12913 and m['output_frames'] == 0 and
             report['public_decode']['decode']['create_status'] == -12913 and report['public_decode']['output_frames'] == 0,
             'video result differs')
        need(log.count('KP_HW_ARM_PASS mode=gva') == 1 and 'KP_HW_ARM_FAIL' not in log and 'KP_HW_HIT_FAIL' not in log and
             log.count('KP_CACHE_CHECK ') == 0 and re.search(r'4\.1: .*resolved, hardware, hit count = 0', log) and
             re.search(r'2\.1: .*resolved, hardware, hit count = 1', log) and
             re.search(r'3\.1: .*resolved, hardware, hit count = 2', log), 'breakpoint evidence differs')
        need(re.search(r'KP_HW_HIT name=property_return bytes_match=1 .*prop_present=0 node_flag_valid=1 node_flag=0', log) and
             len(re.findall(r'KP_HW_HIT name=list_entry bytes_match=1 .*link_valid=1 same_node=1', log)) == 2 and
             'key=IOGVACodec options=0 present=0' in stderr and 'KP_GVA_IMAGE_VALIDATED' in stderr,
             'property/list evidence differs')
        receipts.append({'manifest_sha256': sha(root/'manifest.json'), 'log_sha256': sha(root/'lldb.log'),
                         'cache_breakpoint_hits': 0, 'property_return_hits': 1, 'list_entry_hits': 2,
                         'decoder_status': -12913, 'frames': 0})
    need(receipts[0]['manifest_sha256'] != receipts[1]['manifest_sha256'], 'runs not distinct')
    result = {'status': 'PASS_TWO_BOUNDED_CACHE_BREAKPOINT_OBSERVATIONS', 'runs': receipts,
              'calibration_sha256': sha(a.calibration/'calibration.json'), 'reserved_control_sha256': sha(a.reserved_control/'manifest.json'),
              'build_sha256': sha(a.build/'build.json'), 'audit_source_sha256': sha(Path(__file__)),
              'cache_breakpoint_resolved': True, 'cache_branch_hit_observed': False,
              'cache_read_calibrated_on_real_breakpoint': False, 'node_lifetime_proved': False,
              'cache_path_impossible_proved': False, 'hardware_video_execution_proved': False,
              'counterfactual_property_and_policy_used': True, 'system_modified': False}
    with a.out.open('x') as out:
        json.dump(result, out, indent=2, sort_keys=True); out.write('\n')
    print(json.dumps({'status': result['status'], 'runs': len(receipts), 'cache_breakpoint_hits': 0,
                      'hardware_video_execution_proved': False}))


if __name__ == '__main__': main()
