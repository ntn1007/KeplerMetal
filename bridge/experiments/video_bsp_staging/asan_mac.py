#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Transfer only the parser test sources and run sanitizers on the MacBook."""
import argparse
import base64
import hashlib
import json
import re
import shlex
import subprocess
from pathlib import Path, PurePosixPath
from validate_baseline import EXPECTED

HERE = Path(__file__).resolve().parent
NAMES = ('H264Stream.h', 'H264Stream.cpp', 'H264Baseline.h', 'H264Baseline.cpp', 'test_baseline.cpp', 'baseline_tool.cpp')
OPTS = ['-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=8']


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def command(label, args, out):
    result = subprocess.run(list(map(str, args)), capture_output=True, timeout=120)
    (out / (label + '.stdout')).write_bytes(result.stdout)
    (out / (label + '.stderr')).write_bytes(result.stderr)
    if result.returncode != 0: raise ValueError(label + ' failed; inspect stderr')
    return result.stdout.decode()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--remote-dir',required=True)
    p.add_argument('--host',required=True,help='authenticated SSH alias')
    p.add_argument('--fixture',type=Path,required=True)
    p.add_argument('--baseline',type=Path,required=True)
    a = p.parse_args()
    if a.out.exists() or not a.out.parent.is_dir(): raise ValueError('fresh local output required')
    if (not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]*', a.host) or
        not re.fullmatch(r'/[A-Za-z0-9_./-]+', a.remote_dir) or
        '..' in PurePosixPath(a.remote_dir).parts):
        raise ValueError('invalid host or remote directory')
    ssh = ['ssh','-T',*OPTS,a.host]
    a.out.mkdir()
    before = {n:sha(HERE/n) for n in NAMES}
    if {x.name:sha(x) for x in a.fixture.iterdir() if x.is_file()} != EXPECTED:
        raise ValueError('fixture differs')
    baseline = json.loads((a.baseline/'validation.json').read_text())
    if baseline['status'] != 'PASS_SIX_FFMPEG_BASELINE_HEADERS_CPU' or any(
        baseline['source_sha256'][n] != before[n] for n in NAMES):
        raise ValueError('baseline source differs')
    meta = json.loads((a.fixture/'fixture.json').read_text())
    for i, value in enumerate(meta['H264_parameter_sets_base64']):
        (a.out/('param-%d.bin'%i)).write_bytes(base64.b64decode(value,validate=True))
    data = [a.out/'param-0.bin', a.out/'param-1.bin', *(a.fixture/('frame-%03d.avcc'%i) for i in range(6))]
    data_hashes = {x.name:sha(x) for x in data}
    command('mkdir', [*ssh, 'mkdir ' + shlex.quote(a.remote_dir)], a.out)
    command('transfer', ['scp', *OPTS, *(HERE/n for n in NAMES), a.host + ':' + a.remote_dir + '/'], a.out)
    command('transfer-fixture', ['scp', *OPTS, *data, a.host + ':' + a.remote_dir + '/'], a.out)
    prefix = 'cd ' + shlex.quote(a.remote_dir) + ' && '
    def hashes(label):
        text = command(label, [*ssh, prefix + 'shasum -a 256 ' + ' '.join(NAMES)], a.out)
        pairs = [line.split(None, 1) for line in text.splitlines()]
        result = {name:digest for digest,name in pairs}
        if result != before: raise ValueError(label + ' source hashes differ')
        return result
    hashes('before')
    def verify_fixture(label):
        text = command(label, [*ssh, prefix + 'shasum -a 256 ' + ' '.join(data_hashes)], a.out)
        if {name:digest for digest,name in (line.split(None,1) for line in text.splitlines())} != data_hashes:
            raise ValueError(label + ' fixture hashes differ')
    verify_fixture('fixture-before')
    remote = prefix + ('xcrun clang++ -std=c++17 -Wall -Wextra -Werror -O1 -g '
        '-fsanitize=address,undefined H264Stream.cpp H264Baseline.cpp test_baseline.cpp -o baseline-asan '
        '&& ./baseline-asan && xcrun clang++ -std=c++17 -Wall -Wextra -Werror -O1 -g '
        '-fsanitize=address,undefined H264Stream.cpp H264Baseline.cpp baseline_tool.cpp -o baseline-tool '
        '&& uname -m && xcrun clang++ --version | head -1 && shasum -a 256 baseline-asan baseline-tool')
    lines = command('test', [*ssh,remote], a.out).splitlines()
    if len(lines) != 4 or lines[0] != 'arm64' or not lines[1].startswith('Apple clang version '):
        raise ValueError('remote environment differs')
    compiler_version = lines[1]
    binary_sha, binary_name = lines[2].split(None,1)
    if len(binary_sha) != 64 or binary_name != 'baseline-asan': raise ValueError('remote binary identity differs')
    tool_sha, tool_name = lines[3].split(None,1)
    if len(tool_sha) != 64 or tool_name != 'baseline-tool': raise ValueError('remote tool identity differs')
    sample_names = ['%03d'%i for i in range(6)]
    run = prefix + 'for n in ' + ' '.join(sample_names) + ('; do ./baseline-tool param-0.bin param-1.bin '
          'frame-$n.avcc stage-$n.bin || exit; done; shasum -a 256 ') + ' '.join('stage-%s.bin'%n for n in sample_names)
    lines = command('fixture-test', [*ssh,run], a.out).splitlines()
    if len(lines) != 12: raise ValueError('fixture output count differs')
    for i, name in enumerate(sample_names):
        actual = json.loads(lines[i]); expected = json.loads((a.baseline/('frame-%d.stdout'%i)).read_text())
        digest, filename = lines[6+i].split(None,1)
        if actual != expected or filename != 'stage-%s.bin'%name or digest != baseline['rows'][i]['staged_sha256']:
            raise ValueError('fixture result differs')
    binary_after = command('binaries-after', [*ssh, prefix + 'shasum -a 256 baseline-asan baseline-tool'], a.out)
    if {name:digest for digest,name in (line.split(None,1) for line in binary_after.splitlines())} != {
        'baseline-asan':binary_sha, 'baseline-tool':tool_sha}:
        raise ValueError('remote binaries changed')
    hashes('after')
    verify_fixture('fixture-after')
    if {n:sha(HERE/n) for n in NAMES} != before: raise ValueError('local sources changed')
    if {x.name:sha(x) for x in data} != data_hashes: raise ValueError('local fixture changed')
    receipt = {'status':'PASS_MACBOOK_ASAN_UBSAN', 'architecture':'arm64', 'compiler':compiler_version,
               'source_sha256':before, 'binary_sha256':binary_sha, 'tool_sha256':tool_sha, 'test_exit_code':0,
               'test_stdout_sha256':sha(a.out/'test.stdout'), 'test_stderr_sha256':sha(a.out/'test.stderr'),
               'fixture_stdout_sha256':sha(a.out/'fixture-test.stdout'), 'fixture_stderr_sha256':sha(a.out/'fixture-test.stderr'),
               'baseline_receipt_sha256':sha(a.baseline/'validation.json'), 'real_fixture_frames':6,
               'six_outputs_match_imac':True, 'fixture_sha256':data_hashes,
               'transfer_hashes_match_before_after':True, 'gpu_execution':False,
               'capture_source_sha256':sha(Path(__file__))}
    (a.out/'validation.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(json.dumps(receipt,sort_keys=True))


if __name__ == '__main__': main()
