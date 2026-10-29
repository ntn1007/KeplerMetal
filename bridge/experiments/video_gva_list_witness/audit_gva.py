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
    pattern = r'^KP_HW_HIT name=(after_constructor|list_entry|after_enumeration) bytes_match=([01]) thread=([0-9]+) r14_valid=([01]) r14=([0-9]+) caller_offset=([0-9]+) field_valid=([01]) field=([0-9]+) list_valid=([01]) head_present=([01]) flag=([0-9]+) selector=([0-9]+)$'
    return [(name, *(int(value) for value in values)) for name, *values in re.findall(pattern, log, re.MULTILINE)]


def list_rows(log):
    pattern = r'^KP_LIST_NODE caller_offset=([0-9]+) thread=([0-9]+) index=([0-9]+) kind=([0-9]+) flags=([0-9]+),([0-9]+),([0-9]+),([0-9]+) next_present=([01])$'
    return [tuple(int(value) for value in row) for row in re.findall(pattern, log, re.MULTILINE)]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('base', 'build', 'calibration', 'reserved-control', 'dispatch-region', 'enumerator-region', 'inner-region', 'out'):
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
         c['positive_live_code_bytes_match'] and c['positive_hits'] == {'list_entry': 1, 'after_constructor': 1, 'after_enumeration': 1} and
         c['valid_field_value'] == 7 and c['unreadable_field_refused'] and c['synthetic_head_flag_controls'] and
         c['bounded_cycle_refused'] and
         proof['status'] == 'PASS_RESERVED_DEBUGGER_CPU' and proof['reservation']['state'] == 'terminal' and
         proof['calibration_sha256'] == sha(cal / 'calibration.json') and
         proof['guard_sha256'] == sha(build / 'lldb_guard.py') and proof['log_sha256'] == sha(control / 'lldb.log'),
         'CPU control differs')
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
    dispatch, enumerator = a.dispatch_region.read_bytes(), a.enumerator_region.read_bytes()
    need(sha(a.dispatch_region) == 'cb8e85197a4b37270ced86a070fecb85bb61ea56aa98892996658a304544db0c' and
         sha(a.enumerator_region) == '38281d047ee261127550cff96495d8aa7a911fe889fb6f7a6ac2992f3bbb274c',
         'static code differs')
    callsite = 115791 - 115359
    need(dispatch[callsite - 3:callsite] == bytes.fromhex('4989d8') and dispatch[callsite] == 0xe8 and
         115796 + struct.unpack_from('<i', dispatch, callsite + 1)[0] == 146236 and
         dispatch[callsite + 5:callsite + 10] == bytes.fromhex('31c0833b00'),
         'caller output-pointer flow differs')
    # Callee computes (end - begin) >> 3 and writes its low word via R8,
    # saved in RBX by its prologue. No semantic label for the entries is assumed.
    need(enumerator[9:12] == bytes.fromhex('4c89c3') and
         bytes.fromhex('488b7de0488b45e84829f848c1e8038903') in enumerator,
         'callee count calculation differs')
    inner = a.inner_region.read_bytes()
    need(sha(a.inner_region) == '4c07b6daa5d9e4449c3f77192951ffa230915193befe87cbbf443e25226fa564' and
         inner[55:66] == bytes.fromhex('488b05b66bcd3585d27434') and
         inner[253:281] == bytes.fromhex('80b86104000000750980b86304000000750a488b004885c07451ebe4'),
         'list load or bounded filtering differs')
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
            need(len(found) == 4 and [x[0] for x in found] == ['list_entry', 'after_constructor', 'list_entry', 'after_enumeration'] and
                 all(x[1] == 1 for x in found) and all(x[3:5] == (1, 2) for x in found[1:]) and
                 [x[5] for x in found] == [147562, 264163, 146279, 264163] and
                 len({x[2] for x in found}) == 1 and found[-1][6:8] == (1, 0) and
                 found[0][8:] == found[2][8:] == (1, 1, 0, 2) and
                 found[0][2] != 0 and log.count('KP_HW_ARM_PASS mode=gva') == 1 and
                 log.count('resolved, hardware, hit count = 1') >= 3 and
                 stderr.count('KP_GVA_IMAGE_VALIDATED') == 1, 'current witness differs')
            nodes = list_rows(log)
            thread = found[2][2]
            need(nodes == [(147562, thread, 0, 17039368, 1, 0, 0, 0, 0),
                           (146279, thread, 0, 17039368, 1, 0, 0, 0, 0)] and
                 log.count('KP_LIST_END caller_offset=147562 thread=%d visited=1 reason=end' % thread) == 1 and
                 log.count('KP_LIST_END caller_offset=146279 thread=%d visited=1 reason=end' % thread) == 1,
                 'list snapshot differs')
            registry_line = ('profile=1 id_ok=1 registry=%d class=nvAccelerator key=IOVARendererID' % b['registry_id'])
            need(registry_line in stderr and 'numeric=17039368' in stderr, 'registry numerical comparison differs')
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
                     'same_thread_selector_2_hits': len(found) == 4})
    result = {'status': 'PASS_TWO_SINGLE_NODE_FILTER_OBSERVATIONS', 'runs': 5,
              'current_witness_runs': 2, 'same_thread_selector_2_enumeration_count_zero': 2,
              'wrong_board_controls': 1, 'current_no_marker_controls': 1, 'software_controls': 1,
              'software_images': 6, 'software_reference_bytes': 691200,
              'current_decoder_status': -12913, 'hardware_images': 0,
              'derived_constructor_return_observed': True,
              'base_constructor_return_inferred_from_pinned_flow': True,
              'caller_stack_offsets_at_hits': [147562, 264163, 146279, 264163],
              'enumeration_output_count': 0, 'enumeration_entry_semantics_proved': False,
              'enumerator_live_code_verified_by_marker_and_debugger': True,
              'dispatch_region_sha256': sha(a.dispatch_region), 'enumerator_region_sha256': sha(a.enumerator_region),
              'inner_region_sha256': sha(a.inner_region), 'observed_node_count': 1,
              'inner_live_code_verified_by_marker_and_debugger': True,
              'observed_node_kind_decimal': 17039368, 'observed_node_flags_460_to_463': [1, 0, 0, 0],
              'global_head_nonnull': True, 'selection_flag': 0, 'tail_null': True,
              'registry_renderer_id_matches_numerically': True, 'node_registry_object_identity_proved': False,
              'flag_463_zero_excluded_under_pinned_normal_flow': True, 'node_stability_after_debugger_resume_proved': False,
              'live_object_vtable_readback_proved': False, 'hardware_video_execution_proved': False,
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
