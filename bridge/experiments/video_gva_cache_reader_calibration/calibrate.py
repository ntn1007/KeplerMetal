#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise the actual cache witness callback at four CPU hardware breakpoints."""
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
WITNESS = HERE.parent / 'video_gva_cache_witness'


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(label, argv, out, env=None):
    result = subprocess.run([str(x) for x in argv], capture_output=True, text=True, env=env, timeout=90)
    (out / (label + '.stdout')).write_text(result.stdout)
    (out / (label + '.stderr')).write_text(result.stderr)
    if result.returncode: raise ValueError(label + ' failed: ' + result.stderr[-1000:])
    return result.stdout


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); out = a.out.resolve()
    if out.exists() or not out.parent.is_dir(): raise ValueError('fresh output required')
    out.mkdir()
    files = {'host.cpp': HERE/'host.cpp', 'invoke.S': HERE/'invoke.S', 'lldb_calibrate.py': HERE/'lldb_calibrate.py',
             'lldb_witness.py': WITNESS/'lldb_witness.py', 'marker.S': WITNESS/'marker.S', 'cpu_dylib.cpp': WITNESS/'cpu_dylib.cpp'}
    for name, source in files.items(): shutil.copyfile(source, out/name)
    entitlement = out/'entitlements.plist'
    entitlement.write_bytes(plistlib.dumps({'com.apple.security.get-task-allow': True}))
    host, lib = out/'host', out/'marker.dylib'
    common = ['xcrun', 'clang++', '-arch', 'x86_64', '-O0', '-g', '-Wall', '-Wextra', '-Werror']
    command('build-host', common + [out/'host.cpp', out/'invoke.S', '-o', host], out)
    command('build-lib', common + ['-dynamiclib', out/'cpu_dylib.cpp', out/'marker.S', '-o', lib], out)
    command('sign-host', ['codesign', '--force', '--sign', '-', '--entitlements', entitlement, host], out)
    command('sign-lib', ['codesign', '--force', '--sign', '-', lib], out)
    for binary in (host, lib): command('verify-' + binary.name, ['codesign', '--verify', '--strict', binary], out)
    env = {k:v for k,v in os.environ.items() if not k.startswith(('DYLD_', 'LD_', 'KP_', 'KM_'))}
    lines = ['command script import ' + json.dumps(str(out/'lldb_witness.py')),
             'command script import ' + json.dumps(str(out/'lldb_calibrate.py')),
             'breakpoint set -H -K false -n KPGVAReady', 'breakpoint command add -F lldb_calibrate.arm 1',
             'run', 'breakpoint list', 'quit']
    argv = ['xcrun', 'lldb', '--no-lldbinit', '--batch']
    for line in lines: argv.extend(('-o', line))
    log = command('lldb', argv + ['--', host, lib], out, env)
    negative = command('lldb-wrong-base', argv + ['--', host, lib, 'wrong'], out, env)
    if (negative.count('KP_CACHE_CAL_FAIL base') != 1 or 'KP_CACHE_CAL_ARMED' in negative or
        'KP_CACHE_CHECK ' in negative or 'CACHE_CPU_FINISHED' not in negative or
        'exited with status = 0' not in negative):
        raise ValueError('wrong-base control differs')
    rows = re.findall(r'^KP_CACHE_CHECK thread=(\d+) bytes_match=(\d+) read_ok=(\d+) first_nonzero=(\d+) prior_flag=(\d+)$', log, re.M)
    expected = [('1','1','1','0'), ('1','1','0','1'), ('1','1','1','1'), ('1','0','0','0')]
    if (log.count('KP_CACHE_CAL_ARMED') != 1 or 'KP_CACHE_CAL_FAIL' in log or 'KP_HW_HIT_FAIL' in log or
        len(rows) != 4 or [x[1:] for x in rows] != expected or len({x[0] for x in rows}) != 1 or
        not re.search(r'2\.1: .*resolved, hardware, hit count = 4', log) or
        'CACHE_CPU_FINISHED' not in log or 'exited with status = 0' not in log):
        raise ValueError('hardware breakpoint calibration differs')
    receipt = {'status':'PASS_FOUR_CPU_CACHE_READS', 'read_cases':['nonempty-flag0', 'empty-flag1', 'nonempty-flag1', 'unreadable'],
               'same_thread':True, 'wrong_base_refused':True, 'wrong_base_log_sha256':sha(out/'lldb-wrong-base.stdout'), 'resolved_hardware_breakpoint_hits':4, 'callback_instruction_bytes_match':True,
               'witness_sha256':sha(out/'lldb_witness.py'), 'sources_sha256':{n:sha(out/n) for n in files},
               'host_sha256':sha(host), 'library_sha256':sha(lib), 'lldb_log_sha256':sha(out/'lldb.stdout'),
               'gpu_execution':False, 'vendor_execution':False, 'system_modified':False}
    (out/'calibration.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(json.dumps({'status':receipt['status'], 'hardware_breakpoint_hits':4, 'GPU_execution':False}))


if __name__ == '__main__': main()
