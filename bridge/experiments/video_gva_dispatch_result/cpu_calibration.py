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
    zero = command('zero', lldb + ['zero'], env)
    bad = command('negative', lldb + ['wrong'], env)
    badptr = command('badptr', lldb + ['badptr'], env)
    if (good.count('KP_HW_ARM_PASS mode=cpu') != 1 or
        good.count('KP_HW_HIT name=after_base bytes_match=1') != 1 or
        good.count('KP_HW_HIT name=return_ready bytes_match=1') != 1 or
        not re.search(r'^KP_HW_HIT name=after_enumeration bytes_match=1 .* field_valid=1 field=7 result_valid=0 result=0$', good, re.MULTILINE) or
        'KP_HW_ARM_FAIL' in good or 'KP_HW_HIT_FAIL' in good or
        good.count('resolved, hardware, hit count = 1') < 3 or
        'cpu_value=22' not in good or 'exited with status = 0' not in good):
        raise ValueError('positive control differs')
    if (not re.search(r'^KP_HW_HIT name=return_ready bytes_match=1 .* result_valid=1 result=1$', good, re.MULTILINE) or
        not re.search(r'^KP_HW_HIT name=return_ready bytes_match=1 .* result_valid=1 result=0$', zero, re.MULTILINE) or
        'exited with status = 0' not in zero):
        raise ValueError('return register calibration differs')
    if (bad.count('KP_HW_ARM_FAIL cpu_base') != 1 or 'KP_HW_HIT name=' in bad or
        'KP_HW_ARM_PASS' in bad or 'cpu_value=22' not in bad or 'exited with status = 0' not in bad):
        raise ValueError('negative control differs')
    if (badptr.count('KP_HW_ARM_PASS mode=cpu') != 1 or
        not re.search(r'^KP_HW_HIT name=after_enumeration bytes_match=1 .* field_valid=0 field=0 result_valid=0 result=0$', badptr, re.MULTILINE) or
        'KP_HW_ARM_FAIL' in badptr or 'KP_HW_HIT_FAIL' in badptr or
        'cpu_value=22' not in badptr or 'exited with status = 0' not in badptr):
        raise ValueError('unreadable pointer control differs')
    receipt = {'status': 'PASS_HARDWARE_BREAKPOINT_CPU_CALIBRATION',
               'positive_hits': {'after_base': 1, 'return_ready': 1, 'after_enumeration': 1},
               'positive_live_code_bytes_match': True, 'bad_base_refused': True,
               'valid_field_value': 7, 'unreadable_field_refused': True,
               'return_register_one_and_zero_calibrated': True, 'all_four_processes_exit_zero': True, 'GPU_execution': False,
               'vendor_execution': False, 'system_modified': False,
               'source_sha256': {name: sha(out / name) for name in NAMES},
               'host_sha256': sha(host), 'library_sha256': sha(library),
               'positive_log_sha256': sha(out / 'positive.stdout'),
               'zero_log_sha256': sha(out / 'zero.stdout'),
               'negative_log_sha256': sha(out / 'negative.stdout'),
               'badptr_log_sha256': sha(out / 'badptr.stdout')}
    (out / 'calibration.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__':
    main()
