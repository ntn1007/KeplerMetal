#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run one scoped video host under LLDB and the shared lab reservation."""
import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BRIDGE = HERE.parents[1]
sys.path.insert(0, str(BRIDGE / 'experiments/video_gva_postconstructor_witness'))
from experiment import SYSTEM, identity, sha
sys.path.insert(0, str(HERE.parent / 'video_gva_request_witness'))
from reserved_cpu import LEASE_SHA, terminal_pid


def need(ok, why):
    if not ok:
        raise ValueError(why)


def q(value):
    return json.dumps(str(value))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('lab', 'base', 'build', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--mode', choices=('cpu', 'wrong', 'current'), required=True)
    p.add_argument('--witness', choices=('on', 'off'), default='on')
    a = p.parse_args()
    lab, base, build, out = (getattr(a, n).resolve() for n in ('lab', 'base', 'build', 'out'))
    for path in (base, build, out):
        path.relative_to(lab / 'results')
    need(not out.exists() and out.parent.is_dir(), 'fresh output required')
    b = json.loads((build / 'build.json').read_text())
    old = json.loads((base / 'inputs.json').read_text())
    need(b['status'] == 'PREPARED_ONLY' and b['base_inputs_sha256'] == sha(base / 'inputs.json') and
         b['registry_id'] == identity() and b['system'] == SYSTEM and
         {path: sha(path) for path in SYSTEM} == SYSTEM, 'system profile differs')
    for name, digest in old['frozen'].items():
        need(sha(base / name) == digest, 'base input differs: ' + name)
    for name, digest in b['frozen'].items():
        need(sha(build / name) == digest, 'build input differs: ' + name)
    need(b.get('heap_tracking_variant') and sha(HERE/'lldb_tracking.py')==sha(build/'lldb_tracking.py') and
         sha(HERE/'lldb_target.py')==sha(build/'lldb_target.py') and
         sha(build/'heap-watch.dylib')==b['heap_observer_sha256'], 'heap witness differs')
    parent=HERE.parent/'video_gva_request_witness'
    for name in ('marker.S', 'gva_marker.cpp', 'lldb_witness.py', 'lldb_guard.py'):
        need(sha(parent / name) == sha(build / name), 'current source differs: ' + name)
    lease_path = lab / 'results/video-rm-access-build-20261018-03/runtime/lab_gpu_reservation.py'
    need(sha(lease_path) == LEASE_SHA, 'reservation implementation differs')
    spec = importlib.util.spec_from_file_location('lab_gpu_reservation', lease_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    lease = module.GPUReservation(lab)
    child = None
    proved_terminal = False
    try:
        out.mkdir()
        shutil.copytree(base / 'assets', out / 'assets')
        (out / 'outputs').mkdir()
        host = out / 'application'
        shutil.copyfile(build / 'application', host)
        host.chmod(0o755)
        need(sha(host) == b['frozen']['application'], 'host copy differs')
        (out / 'assets/owned-choice.json').write_text(json.dumps({'route': 'owned'}) + '\n')
        choices = {'dependency-choice.json': 'native' if a.mode == 'cpu' else 'present-key',
                   'factory-policy-choice.json': 'observe' if a.mode == 'cpu' else
                   'wrong-board' if a.mode == 'wrong' else 'current-board'}
        for name, value in choices.items():
            (out / 'assets' / name).write_text(json.dumps({'mode': value}) + '\n')
        for binary in (host, build / 'marker.dylib', base / 'libObserver.dylib'):
            need(subprocess.run(['codesign', '--verify', '--strict', str(binary)], capture_output=True).returncode == 0,
                 'signature differs')
        injected = (str(build / 'marker.dylib') + ':' + str(build / 'heap-watch.dylib') + ':' if a.witness == 'on' else '') + str(base / 'libObserver.dylib')
        target_env = ['DYLD_INSERT_LIBRARIES=' + injected, 'KM_BOARD_MODE=observe', 'KM_GVA_POLICY=none']
        if a.witness == 'on': target_env.append('KP_HEAP_TRACK=1')
        target_args = [out / 'assets', out / 'outputs', 'cpu' if a.mode == 'cpu' else 'hardware']
        commands = [
            'settings set target.env-vars ' + ' '.join(q(x) for x in target_env),
            'settings set target.run-args ' + ' '.join(q(x) for x in target_args),
            'settings set target.output-path ' + q(out / 'stdout.json'),
            'settings set target.error-path ' + q(out / 'stderr.log'),
            'command script import ' + q(build / 'lldb_witness.py'),
            'command script import ' + q(build / 'lldb_guard.py'),
            'command script import ' + q(build / 'lldb_binding.py'),
            'command script import ' + q(build / 'lldb_target.py'),
            'command script import ' + q(build / 'lldb_tracking.py'),
            'breakpoint set -H -K false -n KPGVAReady',
            'breakpoint command add -F lldb_tracking.arm 1',
            'run', 'script lldb_guard.await_terminal(lldb.debugger)', 'breakpoint list', 'quit']
        cmd = ['xcrun', 'lldb', '--no-lldbinit', '--batch']
        for line in commands:
            cmd.extend(('-o', line))
        cmd.extend(('--', str(host)))
        env = {k: v for k, v in os.environ.items() if not k.startswith(('DYLD_', 'LD_', 'KP_', 'KM_'))}
        env['KP_HW_WITNESS_MODE'] = 'gva'
        lease.spawning(host, sha(host))
        with (out / 'lldb.log').open('wb') as log:
            child = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, pass_fds=(lease.fd,), env=env)
            lease.bind_child(child.pid)
            print(json.dumps({'status': 'DEBUGGER_STARTED', 'pid': child.pid, 'mode': a.mode}), flush=True)
            code = child.wait()
        log = (out / 'lldb.log').read_text()
        target_pid = terminal_pid(log)
        table = module.process_table()
        need(child.pid not in table and target_pid not in table and
             not any(row['command'] == str(host) or row['command'].startswith(str(host) + ' ')
                     for row in table.values()), 'debugger or target remains visible')
        proved_terminal = True
        need(code == 0 and not any(x in log for x in ('KP_GUARD_NO_PROCESS', 'KP_GUARD_UNRESOLVED',
             'KP_HW_ARM_FAIL', 'KP_HW_HIT_FAIL', 'KP_HEAP_BINDING_ARM_FAIL')), 'debugger failed or stopped unexpectedly')
        report = json.loads((out / 'stdout.json').read_text())
        need(report['status'] == 'OBSERVATION_COMPLETED' and report['codec'] == 'H264' and
             not report['hardware_video_execution_proved'], 'host report differs')
        need({path: sha(path) for path in SYSTEM} == SYSTEM, 'system profile changed')
        for name, digest in b['frozen'].items():
            need(sha(build / name) == digest, 'build changed: ' + name)
        lease.finish(code, False, '')
        decode = report['public_decode']
        receipt = {'status': 'TERMINAL_SCOPED_DEBUGGER', 'mode': a.mode, 'witness': a.witness,
                   'debugger_pid': child.pid, 'target_pid': target_pid, 'debugger_exit_code': code,
                   'target_exit_code': 0, 'reservation': dict(lease.data),
                   'target_and_debugger_absent': True, 'build_sha256': sha(build / 'build.json'),
                   'host_sha256': sha(host), 'lldb_log_sha256': sha(out / 'lldb.log'),
                   'runner_sha256': sha(Path(__file__)),
                   'stdout_sha256': sha(out / 'stdout.json'), 'stderr_sha256': sha(out / 'stderr.log'),
                   'decoder_status': decode['decode']['create_status'], 'output_frames': decode['output_frames'],
                   'hardware_video_execution_proved': False, 'system_modified': False}
        (out / 'manifest.json').write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
        print(json.dumps({'status': receipt['status'], 'mode': a.mode, 'target_pid': target_pid,
                          'decoder_status': receipt['decoder_status'], 'output_frames': receipt['output_frames']}), flush=True)
    except BaseException:
        if lease.fd is not None:
            if child is None or proved_terminal:
                lease.finish(0, False, '')
            else:
                lease.finish(None, False, 'debugger or target terminal outcome not established')
        raise
    finally:
        lease.close()


if __name__ == '__main__':
    main()
