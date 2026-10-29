#!/usr/bin/env python3
"""Audit transferred native M1 state captures without executing GPU work."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

HERE = Path(__file__).resolve().parent
SOURCE = 'e5f0b89d59a0895e7345ee77aab18cbe80d123150b9c629937811f447f1f465f'
EXECUTABLE = '3a27b0ecf874aa194e8ad8e30e3bcc56a0d3a4be0daabdcb07adcbcc3f843830'


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def need(ok, reason):
    if not ok: raise ValueError(reason)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); root = a.input.resolve()
    need(not a.out.exists() and a.out.parent.is_dir(), 'fresh output required')
    remote = json.loads((root/'remote-hashes.json').read_text())
    captures = [f'captures/{mode}-{i}.bin' for i in range(2) for mode in ('icb','parent')]
    captures.append('captures/untouched.bin')
    need(set(remote) == {'reference', 'state_reference.mm', 'stdout.json', 'stderr.log', *captures} and
         remote['reference'] == EXECUTABLE and remote['state_reference.mm'] == digest(HERE/'state_reference.mm') == SOURCE,
         'source/executable identity')
    for name in captures + ['stdout.json','stderr.log']:
        need(digest(root/name) == remote[name], 'transfer hash: '+name)
    need((root/'stderr.log').read_bytes() == b'', 'stderr differs')
    report = json.loads((root/'stdout.json').read_text())
    need(report.get('status') == 'PASS_NATIVE_STATE_REFERENCE' and report.get('device') == 'Apple M1 Max' and
         report.get('pipeline_order') == ['a','b'] and report.get('indirect_runs') == 2 and
         report.get('direct_after_icb_runs') == 2 and report.get('words_checked') == 256 and
         report.get('control_words') == 64 and report.get('single_encoder') is True and
         report.get('parent_rebound_after_icb') is False and report.get('kepler_gpu_tested') is False and
         report.get('registry_id'), 'host report differs')
    hashes = {}
    for i, base in enumerate((0x1000,0x2000)):
        icb, parent = ((root/f'captures/{mode}-{i}.bin').read_bytes() for mode in ('icb','parent'))
        need(len(icb) == len(parent) == 256 and icb == parent and
             struct.unpack('<64I',parent) == tuple(base+j for j in range(64)), 'capture mismatch')
        hashes[f'pair-{i}'] = hashlib.sha256(parent).hexdigest()
    need((root/'captures/untouched.bin').read_bytes() == b'\xa5'*256, 'control changed')
    result = {'status':'PASS_M1_NATIVE_STATE_REFERENCE','source_sha256':SOURCE,'reference_executable_sha256':EXECUTABLE,
              'remote_stdout_sha256':remote['stdout.json'],'pipeline_order':['a','b'],'indirect_runs':2,
              'direct_after_icb_runs':2,'correct_uint32_values':256,'untouched_control_words':64,
              'single_encoder':True,'parent_pipeline_or_buffer_rebound_after_icb':False,'capture_pair_sha256':hashes,
              'capture_hashes_verified_after_transfer':True,'recorded_process_exit':'observed separately by SSH',
              'kepler_gpu_execution':False,'new_gpu_execution_by_audit':False}
    with a.out.open('x') as out: json.dump(result,out,indent=2,sort_keys=True);out.write('\n')
    print(json.dumps({'status':result['status'],'checked_uint32':256,'gpu_execution_by_audit':False}))


if __name__ == '__main__': main()
