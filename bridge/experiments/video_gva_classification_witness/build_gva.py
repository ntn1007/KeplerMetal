#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build an isolated debugger host and marker without executing vendor code."""
import argparse
import hashlib
import json
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BRIDGE = HERE.parents[1]
sys.path.insert(0, str(BRIDGE / 'experiments/video_gva_postconstructor_witness'))
from experiment import SYSTEM, identity


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def need(ok, why):
    if not ok:
        raise ValueError(why)


def command(argv):
    result = subprocess.run([str(x) for x in argv], capture_output=True, text=True, timeout=90)
    need(result.returncode == 0, str(argv[0]) + ' failed: ' + result.stderr[-1200:])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('lab', 'base', 'calibration', 'reserved-control', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    lab, base, cal, reserved, out = (getattr(a, n).resolve() for n in
                                    ('lab', 'base', 'calibration', 'reserved_control', 'out'))
    for path in (base, cal, reserved, out):
        path.relative_to(lab / 'results')
    need(not out.exists() and out.parent.is_dir(), 'fresh build required')
    original = json.loads((base / 'inputs.json').read_text())
    calibration = json.loads((cal / 'calibration.json').read_text())
    control = json.loads((reserved / 'manifest.json').read_text())
    need(original['new_registry_ID'] == identity() and {path: sha(path) for path in SYSTEM} == SYSTEM,
         'system or device profile differs')
    for name, digest in original['frozen'].items():
        need(sha(base / name) == digest, 'base artifact differs: ' + name)
    need(calibration['status'] == 'PASS_HARDWARE_BREAKPOINT_CPU_CALIBRATION' and
         control['status'] == 'PASS_RESERVED_DEBUGGER_CPU' and control['reservation']['state'] == 'terminal' and
         control['debugger_and_target_absent_from_process_table'] and
         control['calibration_sha256'] == sha(cal / 'calibration.json') and
         control['log_sha256'] == sha(reserved / 'lldb.log') and
         control['guard_sha256'] == sha(HERE / 'lldb_guard.py'), 'CPU control differs')
    for name, digest in calibration['source_sha256'].items():
        need(sha(cal / name) == sha(HERE / name) == digest, 'calibration source differs: ' + name)
    out.mkdir()
    for name in ('marker.S', 'gva_marker.cpp', 'lldb_witness.py', 'lldb_guard.py'):
        shutil.copyfile(HERE / name, out / name)
    host, marker = out / 'application', out / 'marker.dylib'
    shutil.copyfile(base / 'application', host)
    host.chmod(0o755)
    entitlement = out / 'entitlements.plist'
    entitlement.write_bytes(plistlib.dumps({'com.apple.security.get-task-allow': True}))
    command(['xcrun', 'clang++', '-arch', 'x86_64', '-O2', '-std=c++17', '-Wall', '-Wextra', '-Werror',
             '-dynamiclib', out / 'gva_marker.cpp', out / 'marker.S', '-o', marker])
    command(['codesign', '--force', '--sign', '-', marker])
    command(['codesign', '--force', '--sign', '-', '--entitlements', entitlement, host])
    for path in (host, marker, base / 'libObserver.dylib'):
        command(['codesign', '--verify', '--strict', path])
    frozen = {x.name: sha(x) for x in out.iterdir() if x.is_file()}
    receipt = {'status': 'PREPARED_ONLY', 'frozen': frozen, 'base_inputs_sha256': sha(base / 'inputs.json'),
               'base_application_sha256': sha(base / 'application'),
               'calibration_sha256': sha(cal / 'calibration.json'),
               'reserved_control_sha256': sha(reserved / 'manifest.json'),
               'registry_id': original['new_registry_ID'], 'system': SYSTEM,
               'GPU_execution': False, 'vendor_execution': False, 'system_modified': False}
    (out / 'build.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'status': receipt['status'], 'host_sha256': sha(host),
                      'marker_sha256': sha(marker), 'GPU_execution': False}))


if __name__ == '__main__':
    main()
