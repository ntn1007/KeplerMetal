#!/usr/bin/env python3
"""Independently check transferred M1 captures; does not run Metal or use a GPU."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

SOURCE = 'fef542286d3369f4ac970c08158ee44bad1d667ee4a8b5b0b29b42aee84a4883'
EXECUTABLE = 'd304c2597abcd5d7ef6b0d6724f001f655a9f99b25cc6bb05576e3b0bf123c67'
HERE = Path(__file__).resolve().parent


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def need(ok, reason):
    if not ok: raise ValueError(reason)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); root = a.input.resolve()
    need(not a.out.exists() and a.out.parent.is_dir(), 'fresh output required')
    remote = json.loads((root/'remote-hashes.json').read_text())
    captures = [f'captures/{mode}-{i}.bin' for i in range(3) for mode in ('direct', 'icb')]
    captures.append('captures/no-dispatch.bin')
    required = {'reference', 'reference.mm', 'stdout.json', 'stderr.log', *captures}
    need(set(remote) == required and remote['reference'] == EXECUTABLE and
         remote['reference.mm'] == digest(HERE/'reference.mm') == SOURCE, 'source/executable identity')
    for name in captures + ['stdout.json', 'stderr.log']:
        need(digest(root/name) == remote[name], 'transfer hash: '+name)
    need((root/'stderr.log').read_bytes() == b'', 'stderr differs')
    report = json.loads((root/'stdout.json').read_text())
    need(report.get('status') == 'PASS_NATIVE_REFERENCE' and report.get('device') == 'Apple M1 Max' and
         report.get('pipeline_order') == ['a','b','a'] and report.get('direct_runs') == 3 and
         report.get('inherited_icb_runs') == 3 and report.get('checked_values') == 384 and
         report.get('no_dispatch_words') == 64 and report.get('reset_tested') is False and
         report.get('kepler_gpu_tested') is False and report.get('registry_id'), 'host report differs')
    hashes = {}
    for i, base in enumerate((0x1000, 0x2000, 0x1000)):
        expected = tuple(base+j for j in range(64))
        direct, indirect = (root/f'captures/{mode}-{i}.bin' for mode in ('direct', 'icb'))
        d, v = direct.read_bytes(), indirect.read_bytes()
        need(len(d) == len(v) == 256 and d == v and struct.unpack('<64I', d) == expected, 'value mismatch')
        hashes[f'pair-{i}'] = hashlib.sha256(d).hexdigest()
    control = (root/'captures/no-dispatch.bin').read_bytes()
    need(control == b'\xa5'*256, 'no-dispatch control changed')
    result = {'status': 'PASS_M1_NATIVE_COMPUTE_INHERIT_REFERENCE', 'source_sha256': SOURCE,
              'reference_executable_sha256': EXECUTABLE, 'remote_stdout_sha256': remote['stdout.json'],
              'pipeline_order': ['a','b','a'], 'direct_runs': 3, 'indirect_runs': 3,
              'correct_uint32_values': 384, 'no_dispatch_words': 64, 'capture_pair_sha256': hashes,
              'capture_hashes_verified_after_transfer': True, 'recorded_process_exit': 'observed separately by SSH',
              'reset_tested': False, 'kepler_gpu_execution': False, 'new_gpu_execution_by_audit': False,
              'scope': 'native M1 Max, one inherited compute ICB, explicit buffer, serial submissions'}
    with a.out.open('x') as out: json.dump(result, out, indent=2, sort_keys=True); out.write('\n')
    print(json.dumps({'status': result['status'], 'checked_uint32': 384, 'gpu_execution_by_audit': False}))


if __name__ == '__main__': main()
