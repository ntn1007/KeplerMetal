#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise LLDB and a controlled CPU child under the shared lab reservation."""
import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
LEASE_SHA = 'ee637d27c5af482b1fbce396f6a49ef234b09a7d8602aeb36edc422f46b61248'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def need(condition, message):
    if not condition:
        raise ValueError(message)


def terminal_pid(text):
    rows = re.findall(r'^KP_PROCESS_EXITED pid=([0-9]+) code=([0-9]+)$', text, re.MULTILINE)
    need(len(rows) == 1 and int(rows[0][0]) > 0 and rows[0][1] == '0', 'target terminal receipt differs')
    return int(rows[0][0])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('lab', 'calibration', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    a = p.parse_args()
    lab, cal, out = a.lab.resolve(), a.calibration.resolve(), a.out.resolve()
    for path in (cal, out):
        path.relative_to(lab / 'results')
    need(not out.exists() and out.parent.is_dir(), 'fresh output required')
    c = json.loads((cal / 'calibration.json').read_text())
    need(c['status'] == 'PASS_HARDWARE_BREAKPOINT_CPU_CALIBRATION' and
         not c['GPU_execution'] and not c['vendor_execution'], 'calibration differs')
    for name, digest in c['source_sha256'].items():
        need(sha(cal / name) == sha(HERE / name) == digest, 'calibration source differs: ' + name)
    need(sha(cal / 'host') == c['host_sha256'] and sha(cal / 'marker.dylib') == c['library_sha256'],
         'calibration executable differs')
    need(all(sha(cal / (name + '.stdout')) == digest for name, digest in c['logs'].items()) and
         c['excluded_skip_same_node'] and c['accepted_skip_absent'] and c['bad_base_refused'] and
         c['output_field'] == 7, 'calibration logs differ')
    lease_path = lab / 'results/video-rm-access-build-20261018-03/runtime/lab_gpu_reservation.py'
    need(sha(lease_path) == LEASE_SHA, 'reservation implementation differs')
    spec = importlib.util.spec_from_file_location('lab_gpu_reservation', lease_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    lease = module.GPUReservation(lab)
    child = None
    try:
        out.mkdir()
        for name in ('host', 'marker.dylib', 'lldb_witness.py'):
            shutil.copyfile(cal / name, out / name)
        shutil.copyfile(HERE / 'lldb_guard.py', out / 'lldb_guard.py')
        host = out / 'host'
        host.chmod(0o755)
        need(sha(host) == c['host_sha256'] and sha(out / 'marker.dylib') == c['library_sha256'],
             'copied executable differs')
        for binary in (host, out / 'marker.dylib'):
            need(subprocess.run(['codesign', '--verify', '--strict', str(binary)], capture_output=True).returncode == 0,
                 'signature differs')
        cmd = ['xcrun', 'lldb', '--no-lldbinit', '--batch',
               '-o', 'command script import ' + json.dumps(str(out / 'lldb_witness.py')),
               '-o', 'command script import ' + json.dumps(str(out / 'lldb_guard.py')),
               '-o', 'breakpoint set -H -K false -n KPGVAReady',
               '-o', 'breakpoint command add -F lldb_witness.arm 1', '-o', 'run',
               '-o', 'script lldb_guard.await_terminal(lldb.debugger)',
               '-o', 'breakpoint list', '-o', 'quit', '--', str(host), str(out / 'marker.dylib')]
        env = {k: v for k, v in os.environ.items() if not k.startswith(('DYLD_', 'LD_', 'KP_'))}
        env['KP_HW_WITNESS_MODE'] = 'cpu'
        lease.spawning(host, sha(host))
        with (out / 'lldb.log').open('wb') as log:
            child = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, pass_fds=(lease.fd,), env=env)
            lease.bind_child(child.pid)
            print(json.dumps({'status': 'DEBUGGER_STARTED', 'pid': child.pid}), flush=True)
            code = child.wait()
        log = (out / 'lldb.log').read_text()
        target_pid = terminal_pid(log)
        need(code == 0 and log.count('KP_HW_ARM_PASS mode=cpu') == 1 and
             re.search(r'KP_CLASS_HIT name=classify bytes_match=1 .*kind_valid=1 kind=17039368', log) and
             re.search(r'KP_CLASS_HIT name=skip bytes_match=1 .*same_prior=1', log) and
             re.search(r'KP_CLASS_HIT name=after_enumeration bytes_match=1 .*field_valid=1 field=7', log) and
             'KP_HW_ARM_FAIL' not in log and 'KP_HW_HIT_FAIL' not in log and 'cpu_value=22' in log,
             'debugger output differs')
        table = module.process_table()
        need(child.pid not in table and target_pid not in table and
             not any(row['command'] == str(host) or row['command'].startswith(str(host) + ' ') for row in table.values()),
             'debugger or controlled target still visible')
        lease.finish(code, False, '')
        receipt = {'status': 'PASS_RESERVED_DEBUGGER_CPU', 'debugger_pid': child.pid,
                   'target_pid': target_pid, 'target_exit_code': 0, 'debugger_exit_code': code,
                   'debugger_and_target_absent_from_process_table': True,
                   'reservation': dict(lease.data), 'log_sha256': sha(out / 'lldb.log'),
                   'calibration_sha256': sha(cal / 'calibration.json'),
                   'host_sha256': sha(host), 'marker_sha256': sha(out / 'marker.dylib'),
                   'guard_sha256': sha(out / 'lldb_guard.py'),
                   'GPU_execution': False, 'vendor_execution': False, 'system_modified': False}
        (out / 'manifest.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
        print(json.dumps({'status': receipt['status'], 'target_pid': target_pid,
                          'debugger_pid': child.pid, 'GPU_execution': False}), flush=True)
    except BaseException:
        # A missing target-exit receipt is not a terminal result, even if LLDB exited.
        if lease.fd is not None:
            if child is None:
                lease.finish(0, False, '')
            else:
                lease.finish(None, False, 'debugger or target terminal outcome not established')
        raise
    finally:
        lease.close()


if __name__ == '__main__':
    main()
