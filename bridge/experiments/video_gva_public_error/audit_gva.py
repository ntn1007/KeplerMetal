#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit scoped debugger receipts without launching vendor code or the GPU."""
import argparse
import json
import re
import struct
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BRIDGE = HERE.parents[1]
sys.path.insert(0, str(BRIDGE / 'experiments/video_gva_postconstructor_witness'))
from experiment import SYSTEM, sha
sys.path.insert(0, str(HERE))
from reserved_cpu import terminal_pid


def need(ok, why):
    if not ok:
        raise ValueError(why)


def read(path):
    return json.loads(Path(path).read_text())


def signature(path):
    need(subprocess.run(['codesign', '--verify', '--strict', str(path)], capture_output=True).returncode == 0,
         'signature differs')


def hits(log):
    pattern = r'^KP_HW_HIT name=(failure_path|gva_exit|vt_return) bytes_match=([01]) thread=([0-9]+) result_valid=([01]) result=(-?[0-9]+) caller_vt_match=([01])$'
    return [(name, int(match), int(thread), int(valid), int(result), int(caller))
            for name, match, thread, valid, result, caller in re.findall(pattern, log, re.M)]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'build', 'calibration', 'reserved-control', 'context-region', 'vt-region', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--runs', type=Path, nargs=5, required=True)
    a = p.parse_args()
    need(not a.out.exists() and a.out.parent.is_dir() and len(set(a.runs)) == 5, 'fresh output or runs differ')
    base, build, cal, control = (getattr(a, name).resolve() for name in
                                  ('base', 'build', 'calibration', 'reserved_control'))
    b, old, c, proof = (read(build / 'build.json'), read(base / 'inputs.json'),
                         read(cal / 'calibration.json'), read(control / 'manifest.json'))
    need(b['status'] == 'PREPARED_ONLY' and b['base_inputs_sha256'] == sha(base / 'inputs.json') and
         b['calibration_sha256'] == sha(cal / 'calibration.json') and
         b['reserved_control_sha256'] == sha(control / 'manifest.json') and b['system'] == SYSTEM and
         {path: sha(path) for path in SYSTEM} == SYSTEM, 'build or system differs')
    need(c['status'] == 'PASS_HARDWARE_BREAKPOINT_CPU_CALIBRATION' and c['bad_base_refused'] and
         c['signed_negative_and_zero_calibrated'] and c['positive_log_sha256'] == sha(cal / 'positive.stdout') and
         c['zero_log_sha256'] == sha(cal / 'zero.stdout') and
         proof['status'] == 'PASS_RESERVED_DEBUGGER_CPU' and proof['reservation']['state'] == 'terminal' and
         proof['calibration_sha256'] == sha(cal / 'calibration.json') and
         proof['guard_sha256'] == sha(build / 'lldb_guard.py') and proof['log_sha256'] == sha(control / 'lldb.log'),
         'CPU control differs')
    for label, expected in [('positive', -12913), ('zero', 0)]:
        calibration_hits = hits((cal / (label + '.stdout')).read_text())
        need([x[0] for x in calibration_hits] == ['failure_path','gva_exit','vt_return'] and
             all(x[1] == 1 for x in calibration_hits) and
             all(x[3:5] == (1, expected) for x in calibration_hits[1:]) and
             all(x[5] == 0 for x in calibration_hits), 'calibration observations differ')
    for name, digest in old['frozen'].items():
        need(sha(base / name) == digest, 'base differs: ' + name)
    for name, digest in b['frozen'].items():
        need(sha(build / name) == digest, 'build differs: ' + name)
    for name in ('marker.S', 'gva_marker.cpp', 'lldb_witness.py', 'lldb_guard.py'):
        need(sha(build / name) == sha(HERE / name), 'source differs: ' + name)
    for name, digest in c['source_sha256'].items():
        need(sha(cal / name) == sha(HERE / name) == digest, 'calibration source differs')
    signature(build / 'marker.dylib')
    signature(base / 'libObserver.dylib')
    context, vt = a.context_region.read_bytes(), a.vt_region.read_bytes()
    need(sha(a.context_region) == '2ce45fe6c3ffc591e794e46655393ba2848540f55c891bfbf1f189e6d0e4c9e0' and
         context[263877-262270:263883-262270] == bytes.fromhex('41bc8fcdffff') and
         context[262330-262270:262333-262270] == bytes.fromhex('4489e0'), 'context return sequence differs')
    need(sha(a.vt_region) == 'f3cb75d0d4d4c97e2ca66ed815bd0fa636d96f6c955ba98d0fe8be39860a7a60' and
         vt[4300698-4298704-3:4300698-4298704+5] == bytes.fromhex('ff50084189c685c0'),
         'VideoToolbox call sequence differs')
    pattern = [('cpu', 'on', 0, 6), ('current', 'on', -12913, 0), ('wrong', 'on', -12906, 0),
               ('current', 'off', -12913, 0), ('current', 'on', -12913, 0)]
    rows = []
    runner_pins = []
    for root, (mode, witness, status, frames) in zip(a.runs, pattern):
        root = root.resolve()
        m, report = read(root / 'manifest.json'), read(root / 'stdout.json')
        log, stderr = (root / 'lldb.log').read_text(), (root / 'stderr.log').read_text()
        need(m['status'] == 'TERMINAL_SCOPED_DEBUGGER' and m['mode'] == mode and m['witness'] == witness and
             m['decoder_status'] == status and m['output_frames'] == frames and
             m['target_exit_code'] == m['debugger_exit_code'] == 0 and m['target_and_debugger_absent'] and
             m['reservation']['state'] == 'terminal' and m['reservation']['child_PID'] == m['debugger_pid'] and
             m['reservation']['child_birth_observed'] and not m['reservation']['SIGKILL_requested'] and
             not m['reservation']['authoritative_ps_status'] and m['build_sha256'] == sha(build / 'build.json') and
             m['host_sha256'] == sha(root / 'application') == b['frozen']['application'] and
             m['lldb_log_sha256'] == sha(root / 'lldb.log') and m['stdout_sha256'] == sha(root / 'stdout.json') and
             m['stderr_sha256'] == sha(root / 'stderr.log') and terminal_pid(log) == m['target_pid'], 'run receipt differs')
        signature(root / 'application')
        if 'runner_sha256' in m:
            need(m['runner_sha256'] == sha(HERE / 'run_gva.py'), 'runner source differs')
        runner_pins.append('runner_sha256' in m)
        need(report['status'] == 'OBSERVATION_COMPLETED' and report['codec'] == 'H264' and
             not report['hardware_video_execution_proved'], 'host report differs')
        decode = report['public_decode']
        need(decode['decode']['create_status'] == status and decode['output_frames'] == frames, 'decode differs')
        choices = {'assets/owned-choice.json', 'assets/dependency-choice.json', 'assets/factory-policy-choice.json'}
        for name, digest in old['frozen'].items():
            if name.startswith('assets/') and name not in choices:
                need(sha(root / name) == digest, 'asset differs: ' + name)
        need(read(root / 'assets/owned-choice.json') == {'route': 'owned'} and
             read(root / 'assets/dependency-choice.json') == {'mode': 'native' if mode == 'cpu' else 'present-key'} and
             read(root / 'assets/factory-policy-choice.json') == {'mode': 'observe' if mode == 'cpu' else
                  'wrong-board' if mode == 'wrong' else 'current-board'}, 'configuration differs')
        found = hits(log)
        need('KP_HW_ARM_FAIL' not in log and 'KP_HW_HIT_FAIL' not in log and 'KP_GUARD_UNRESOLVED' not in log,
             'debugger error recorded')
        if mode == 'current' and witness == 'on':
            need(len(found) == 3 and [x[0] for x in found] == ['failure_path', 'gva_exit', 'vt_return'] and
                 all(x[1] == 1 for x in found) and all(x[3:5] == (1, -12913) for x in found[1:]) and
                 found[1][5] == 1 and found[0][2] == found[1][2] == found[2][2] and found[0][2] != 0 and
                 log.count('KP_HW_ARM_PASS mode=gva') == 1 and log.count('resolved, hardware, hit count = 1') >= 4 and
                 stderr.count('KP_GVA_IMAGE_VALIDATED') == 1, 'current witness differs')
        elif mode == 'wrong':
            need(not found and log.count('KP_HW_ARM_PASS mode=gva') == 1 and
                 log.count('resolved, hardware, hit count = 0') >= 3, 'wrong-board witness differs')
        else:
            need(not found and 'KP_HW_ARM_PASS' not in log, 'unexpected witness')
        if mode == 'cpu':
            need(decode['different_bytes'] == 0 and decode['CPU_reference_bytes_compared'] == 691200,
                 'software report differs')
            for i in range(6):
                data = (root / 'outputs' / ('vt-frame-%03d.nv12' % i)).read_bytes()
                reference = (root / 'assets/fixtures/H264' / ('cpu-frame-%03d.nv12' % i)).read_bytes()
                need(len(data) == 115200 and data == reference, 'software frame differs')
        rows.append({'mode': mode, 'witness': witness, 'decoder_status': status, 'frames': frames,
                     'same_thread_return_chain': len(found) == 3})
    result = {'status': 'PASS_TWO_DIRECT_VIDEOTOOLBOX_ERROR_RETURNS', 'runs': 5,
              'current_witness_runs': 2, 'same_thread_direct_error_returns': 2,
              'wrong_board_controls': 1, 'current_no_marker_controls': 1, 'software_controls': 1,
              'software_images': 6, 'software_reference_bytes': 691200,
              'gva_return': -12913, 'videotoolbox_postcall_result': -12913,
              'public_decoder_status': -12913, 'hardware_images': 0,
              'context_region_sha256': sha(a.context_region), 'vt_region_sha256': sha(a.vt_region),
              'runtime_direct_caller_match': True, 'hardware_video_execution_proved': False,
              'counterfactual_property_and_policy_used': True, 'debugger_may_change_timing': True,
              'runner_source_hash_recorded_in_original_receipts': all(runner_pins),
              'build_sha256': sha(build / 'build.json'), 'calibration_sha256': sha(cal / 'calibration.json'),
              'run_receipt_sha256': [sha(root / 'manifest.json') for root in a.runs],
              'audit_source_sha256': sha(Path(__file__)), 'receipts': rows,
              'vendor_or_GPU_execution_during_audit': False, 'system_modified': False}
    with a.out.open('x') as f:
        json.dump(result, f, indent=2, sort_keys=True)
        f.write('\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
