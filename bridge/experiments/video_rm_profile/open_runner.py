#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run one signed no-RM open probe under the lab lease without killing it."""
import argparse
import datetime
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path

RESERVATION_SHA = 'ee637d27c5af482b1fbce396f6a49ef234b09a7d8602aeb36edc422f46b61248'

def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def stamp(): return datetime.datetime.now(datetime.timezone.utc).isoformat()

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lab', type=Path, required=True)
    p.add_argument('--exe', type=Path, required=True)
    p.add_argument('--sha256', required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--mode', choices=('observe', 'open', 'wrong-code-hash'), required=True)
    p.add_argument('--registry-id', type=int, required=True)
    a = p.parse_args(); root = a.lab.resolve(); exe = a.exe.resolve(); out = a.out.resolve()
    exe.relative_to(root / 'results'); out.relative_to(root / 'results')
    if not a.registry_id or a.registry_id < 0 or os.getuid() != os.geteuid() or not os.getuid():
        raise ValueError('unprivileged caller and positive registry ID required')
    if out.exists() or sha(exe) != a.sha256 or len(a.sha256) != 64:
        raise ValueError('fresh output and exact executable hash required')
    module = root / 'results/video-rm-access-build-20261018-03/runtime/lab_gpu_reservation.py'
    if sha(module) != RESERVATION_SHA: raise ValueError('reservation module changed')
    spec = importlib.util.spec_from_file_location('lab_gpu_reservation', module)
    reservation_module = importlib.util.module_from_spec(spec); spec.loader.exec_module(reservation_module)
    lease = reservation_module.GPUReservation(root)
    child = None
    try:
        out.mkdir(parents=True, exist_ok=False)
        listing = subprocess.run(['otool', '-L', str(exe)], capture_output=True, text=True, check=True, timeout=15)
        if '@loader_path/' in listing.stdout or '@executable_path/' in listing.stdout:
            raise ValueError('relative dependencies require a separate qualification')
        signed = out / 'application'; shutil.copyfile(exe, signed); signed.chmod(0o755)
        subprocess.run(['codesign', '--force', '--sign', '-', str(signed)], check=True, capture_output=True, timeout=15)
        subprocess.run(['codesign', '--verify', '--strict', str(signed)], check=True, capture_output=True, timeout=15)
        signed_hash = sha(signed); lease.spawning(signed, signed_hash)
        registry = root / 'results/signed-native-jobs.json'
        jobs = json.loads(registry.read_text()) if registry.exists() else []
        with (out / 'execution.stdout').open('wb') as stdout, (out / 'execution.stderr').open('wb') as stderr:
            started = stamp()
            child = subprocess.Popen([str(signed), a.mode, str(a.registry_id)], stdout=stdout, stderr=stderr,
                                     pass_fds=(lease.fd,))
            lease.bind_child(child.pid)
            job = {'started_at': started, 'pid': child.pid, 'original_executable': str(exe),
                   'original_binary_sha256': a.sha256, 'signed_executable': str(signed),
                   'signed_binary_sha256': signed_hash, 'arguments': [a.mode, str(a.registry_id)]}
            jobs.append(job); registry.write_text(json.dumps(jobs, indent=2) + '\n')
            print(json.dumps({'status': 'STARTED', 'pid': child.pid}), flush=True)
            code = child.wait()  # No timeout, kill, or automatic retry.
        ps = subprocess.run(['ps', '-p', str(child.pid), '-o', 'pid=,lstart=,command='],
                            capture_output=True, text=True, timeout=10)
        if ps.returncode not in (0, 1) or ps.stderr: raise RuntimeError('process state cannot be verified')
        state = ps.stdout.strip(); job.update(exit_code=code, SIGKILL_requested=False,
            authoritative_ps_status=state, completed_at=stamp())
        registry.write_text(json.dumps(jobs, indent=2) + '\n')
        lease.finish(code, False, state)
        manifest = {**job, 'GPU_reservation': dict(lease.data), 'reservation_module_SHA256': RESERVATION_SHA,
                    'runner_SHA256': sha(__file__), 'kill_requested': False}
        (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        if code or state: raise RuntimeError('inspect this specific process before any retry')
        print((out / 'execution.stdout').read_text().strip(), flush=True)
    except BaseException:
        if child is not None and child.poll() is None:
            lease.finish(None, False, 'child outcome not established')
        raise
    finally:
        lease.close()

if __name__ == '__main__': main()
