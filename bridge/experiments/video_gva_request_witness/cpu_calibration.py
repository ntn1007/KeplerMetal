#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Calibrate two dynamic hardware breakpoints on an original CPU program."""
import argparse
import hashlib
import json
import os
import plistlib
import re
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAMES = ('cpu_dynamic_host.cpp', 'cpu_invoke.S', 'cpu_dylib.cpp', 'marker.S', 'lldb_witness.py')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out', type=Path, required=True)
    args = p.parse_args()
    out = args.out.resolve()
    if out.exists() or not out.parent.is_dir():
        raise ValueError('fresh output required')
    out.mkdir()
    for name in NAMES:
        shutil.copyfile(HERE / name, out / name)
    entitlement = out / 'entitlements.plist'
    entitlement.write_bytes(plistlib.dumps({'com.apple.security.get-task-allow': True}))
    host, library = out / 'host', out / 'marker.dylib'
    common = ['xcrun', 'clang++', '-arch', 'x86_64', '-O0', '-g', '-Wall', '-Wextra', '-Werror']
    def command(label, argv, env=None):
        result = subprocess.run([str(x) for x in argv], capture_output=True, text=True, env=env)
        (out / (label + '.stdout')).write_text(result.stdout)
        (out / (label + '.stderr')).write_text(result.stderr)
        if result.returncode:
            raise ValueError(label + ' failed: ' + result.stderr[-1000:])
        return result.stdout
    command('build-host', common + [out / 'cpu_dynamic_host.cpp', out / 'cpu_invoke.S', '-o', host])
    command('build-library', common + ['-dynamiclib', out / 'cpu_dylib.cpp', out / 'marker.S', '-o', library])
    command('sign-host', ['codesign', '--force', '--sign', '-', '--entitlements', entitlement, host])
    command('sign-library', ['codesign', '--force', '--sign', '-', library])
    for name, binary in [('host', host), ('library', library)]:
        command('verify-' + name, ['codesign', '--verify', '--strict', binary])
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DYLD_', 'LD_', 'KP_'))}
    env['KP_HW_WITNESS_MODE'] = 'cpu'
    lldb = ['xcrun', 'lldb', '--no-lldbinit', '--batch',
            '-o', 'command script import ' + json.dumps(str(out / 'lldb_witness.py')),
            '-o', 'breakpoint set -H -K false -n KPGVAReady',
            '-o', 'breakpoint command add -F lldb_witness.arm 1', '-o', 'run',
            '-o', 'breakpoint list', '-o', 'quit', '--', host, library]
    good = command('positive', lldb, env)
    bad = command('negative', lldb + ['wrong'], env)
    badptr = command('badptr', lldb + ['badptr'], env)
    emptyhead = command('emptyhead', lldb + ['emptyhead'], env)
    cycle = command('cycle', lldb + ['cycle'], env)
    present = command('present', lldb + ['present'], env)
    different = command('different', lldb + ['different'], env)
    active = command('armactive', lldb + ['armactive'], env)
    if 'KP_REQUEST_ARM window=1' not in active or active.count('KP_REQUEST_HIT ') != 3 or 'exited with status = 0' not in active:
        raise ValueError('active-arm control differs')
    windows = command('windows', lldb + ['windows'], env)
    phase_rows = re.findall(r'^KP_REQUEST_HIT name=(property_return|list_entry|after_enumeration) thread=[0-9]+ request_window=([0-3])$', windows, re.MULTILINE)
    if phase_rows != [(name, str(i)) for i in (1, 2, 3) for name in ('property_return', 'list_entry', 'after_enumeration')] or 'exited with status = 0' not in windows:
        raise ValueError('request window calibration differs')
    if (good.count('KP_HW_ARM_PASS mode=cpu') != 1 or
        not re.search(r'^KP_HW_HIT name=property_return bytes_match=1 .* prop_valid=1 prop_present=0 node_flag_valid=1 node_flag=1 link_valid=0 same_node=0$', good, re.MULTILINE) or
        not re.search(r'^KP_HW_HIT name=list_entry bytes_match=1 .* list_valid=1 head_present=1 flag=1 selector=2 .* link_valid=1 same_node=1$', good, re.MULTILINE) or
        not re.search(r'^KP_HW_HIT name=after_enumeration bytes_match=1 .* field_valid=1 field=7 ', good, re.MULTILINE) or
        'KP_HW_ARM_FAIL' in good or 'KP_HW_HIT_FAIL' in good or
        good.count('resolved, hardware, hit count = 1') < 3 or
        len(re.findall(r'^KP_REQUEST_HIT name=(?:property_return|list_entry|after_enumeration) thread=[0-9]+ request_window=1$', good, re.MULTILINE)) != 3 or
        not re.search(r'^KP_LIST_NODE caller_offset=0 thread=[0-9]+ index=0 kind=17301505 flags=0,0,0,1 next_present=1$', good, re.MULTILINE) or
        not re.search(r'^KP_LIST_NODE caller_offset=0 thread=[0-9]+ index=1 kind=16908288 flags=0,1,0,0 next_present=0$', good, re.MULTILINE) or
        not re.search(r'^KP_LIST_END caller_offset=0 thread=[0-9]+ visited=2 reason=end$', good, re.MULTILINE) or
        'cpu_value=22' not in good or 'exited with status = 0' not in good):
        raise ValueError('positive control differs')
    if (bad.count('KP_HW_ARM_FAIL cpu_base') != 1 or 'KP_HW_HIT name=' in bad or
        'KP_HW_ARM_PASS' in bad or 'cpu_value=22' not in bad or 'exited with status = 0' not in bad):
        raise ValueError('negative control differs')
    if (badptr.count('KP_HW_ARM_PASS mode=cpu') != 1 or
        not re.search(r'^KP_HW_HIT name=after_enumeration bytes_match=1 .* field_valid=0 field=0 ', badptr, re.MULTILINE) or
        'KP_HW_ARM_FAIL' in badptr or 'KP_HW_HIT_FAIL' in badptr or
        'cpu_value=22' not in badptr or 'exited with status = 0' not in badptr):
        raise ValueError('unreadable pointer control differs')
    if (emptyhead.count('KP_HW_ARM_PASS mode=cpu') != 1 or
        not re.search(r'^KP_HW_HIT name=list_entry bytes_match=1 .* list_valid=1 head_present=0 flag=0 selector=2 .* link_valid=0 same_node=0$', emptyhead, re.MULTILINE) or
        'KP_HW_ARM_FAIL' in emptyhead or 'KP_HW_HIT_FAIL' in emptyhead or
        'cpu_value=22' not in emptyhead or 'exited with status = 0' not in emptyhead):
        raise ValueError('empty head control differs')
    if (not re.search(r'^KP_LIST_END caller_offset=0 thread=[0-9]+ visited=0 reason=end$', emptyhead, re.MULTILINE) or
        not re.search(r'^KP_LIST_END caller_offset=0 thread=[0-9]+ visited=2 reason=cycle$', cycle, re.MULTILINE) or
        'KP_HW_ARM_FAIL' in cycle or 'KP_HW_HIT_FAIL' in cycle or
        'cpu_value=22' not in cycle or 'exited with status = 0' not in cycle):
        raise ValueError('bounded list controls differ')
    if (not re.search(r'^KP_HW_HIT name=property_return bytes_match=1 .* prop_valid=1 prop_present=1 node_flag_valid=1 node_flag=1 ', present, re.MULTILINE) or
        not re.search(r'^KP_HW_HIT name=list_entry bytes_match=1 .* link_valid=1 same_node=0$', different, re.MULTILINE) or
        any('KP_HW_ARM_FAIL' in log or 'KP_HW_HIT_FAIL' in log or 'cpu_value=22' not in log or
            'exited with status = 0' not in log for log in (present, different))):
        raise ValueError('property and node identity controls differ')
    receipt = {'status': 'PASS_HARDWARE_BREAKPOINT_CPU_CALIBRATION',
               'positive_hits': {'list_entry': 1, 'property_return': 1, 'after_enumeration': 1},
               'positive_live_code_bytes_match': True, 'request_window_1_hits': 3, 'request_windows_1_2_3_calibrated': True, 'active_arm_calibrated': True, 'active_arm_log_sha256': sha(out / 'armactive.stdout'), 'windows_log_sha256': sha(out / 'windows.stdout'), 'bad_base_refused': True,
               'valid_field_value': 7, 'unreadable_field_refused': True,
               'synthetic_head_flag_controls': True, 'bounded_cycle_refused': True,
               'property_present_and_different_node_controls': True,
               'all_seven_processes_exit_zero': True, 'GPU_execution': False,
               'vendor_execution': False, 'system_modified': False,
               'source_sha256': {name: sha(out / name) for name in NAMES},
               'host_sha256': sha(host), 'library_sha256': sha(library),
               'positive_log_sha256': sha(out / 'positive.stdout'),
               'negative_log_sha256': sha(out / 'negative.stdout'),
               'badptr_log_sha256': sha(out / 'badptr.stdout'),
               'emptyhead_log_sha256': sha(out / 'emptyhead.stdout'),
               'cycle_log_sha256': sha(out / 'cycle.stdout'), 'present_log_sha256': sha(out / 'present.stdout'),
               'different_log_sha256': sha(out / 'different.stdout')}
    (out / 'calibration.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
