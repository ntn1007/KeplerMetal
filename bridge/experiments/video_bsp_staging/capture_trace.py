#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Capture a read-only FFmpeg header trace from the authorized MacBook."""
import argparse
import hashlib
import json
import re
import shlex
import subprocess
from pathlib import Path

FIXTURE_SHA = '12858642f02b0e1d98ddf409dd729a879b6a7a5d3434c860882532ca4f6b40af'
SSH_OPTIONS = ['-T', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=8']


def sha(data): return hashlib.sha256(data).hexdigest()
def call(host, remote):
    result = subprocess.run(['ssh', *SSH_OPTIONS, host, remote], capture_output=True, timeout=90)
    if result.returncode != 0:
        raise ValueError('remote command failed: ' + result.stderr.decode('utf-8', 'replace')[-500:])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--host', required=True, help='authenticated SSH alias')
    parser.add_argument('--remote-ffmpeg', required=True)
    parser.add_argument('--remote-fixture', required=True)
    a = parser.parse_args()
    if a.out.exists() or not a.out.parent.is_dir(): raise ValueError('fresh output required')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', a.host) or any(
        not x.startswith('/') or '\n' in x or '\r' in x or '\0' in x for x in (a.remote_ffmpeg,a.remote_fixture)):
        raise ValueError('invalid host or remote path')
    a.out.mkdir()
    ffmpeg, fixture = shlex.quote(a.remote_ffmpeg), shlex.quote(a.remote_fixture)
    identity_cmd = 'uname -m; ' + ffmpeg + ' -version | head -1; shasum -a 256 ' + ffmpeg + ' ' + fixture
    before = call(a.host, identity_cmd).stdout
    (a.out / 'before.txt').write_bytes(before)
    lines = before.decode().splitlines()
    if len(lines) != 4 or lines[0] != 'arm64' or not lines[1].startswith('ffmpeg version '):
        raise ValueError('reference identity differs')
    binary_sha, binary_path = lines[2].split(None, 1)
    fixture_sha, fixture_path = lines[3].split(None, 1)
    if len(binary_sha) != 64 or binary_path != a.remote_ffmpeg or fixture_sha != FIXTURE_SHA or fixture_path != a.remote_fixture:
        raise ValueError('reference input differs')
    command = ffmpeg + ' -hide_banner -nostdin -loglevel verbose -i ' + fixture + ' -c:v copy -bsf:v trace_headers -f null -'
    trace = call(a.host, command)
    (a.out / 'trace.txt').write_bytes(trace.stderr)
    (a.out / 'stdout.txt').write_bytes(trace.stdout)
    after = call(a.host, identity_cmd).stdout
    (a.out / 'after.txt').write_bytes(after)
    if before != after or b'Slice Header' not in trace.stderr:
        raise ValueError('reference changed or trace missing')
    receipt = {'status': 'PASS_FFMPEG_TRACE_CAPTURE', 'architecture': 'arm64', 'ffmpeg_version': lines[1],
               'binary_sha256_before_after': binary_sha, 'fixture_sha256_before_after': fixture_sha,
               'trace_sha256': sha(trace.stderr), 'stdout_sha256': sha(trace.stdout),
               'before_sha256': sha(before), 'after_sha256': sha(after),
               'capture_source_sha256': sha(Path(__file__).read_bytes()),
               'operation': 'stream copy and header trace', 'exit_code': trace.returncode,
               'hardware_decode': False, 'remote_files_written': False}
    (a.out / 'receipt.json').write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps(receipt, sort_keys=True))


if __name__ == '__main__': main()
