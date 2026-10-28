#!/usr/bin/env python3
"""Reproduce explicit CAS-pointer inspection from pinned local AIR, offline."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from inspect_cas_pointer import inspect


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lab', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); lab = a.lab.resolve(); out = a.out.resolve(); out.relative_to(lab / 'results')
    if out.exists() or not out.parent.is_dir(): raise ValueError('fresh output required')
    source = Path(__file__).with_name('cfg_detail_dump.c'); out.mkdir()
    env = {k:v for k,v in os.environ.items() if not k.startswith(('DYLD_', 'LD_'))}
    build_cfg = subprocess.run([sys.executable, str(Path(__file__).with_name('reproduce_air_cfg.py')),
                               '--lab', str(lab), '--out', str(out / 'cfg')],
                              capture_output=True, env=env, timeout=120)
    (out / 'cfg.stderr').write_bytes(build_cfg.stderr)
    if build_cfg.returncode != 0: raise ValueError('previous CFG reproduction failed')
    vendor = lab / 'vendor/OpenNVDA-da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5/drivers/NVMTLDriver/air'
    cmd = ['clang', '-O2', '-I' + str(vendor), str(source), str(lab / 'build/air-bitstream.o'),
           str(lab / 'build/air-airir.o'), '-o', str(out / 'reader')]
    built = subprocess.run(cmd, capture_output=True, env=env, timeout=60)
    (out / 'build.stderr').write_bytes(built.stderr)
    if built.returncode != 0: raise ValueError('detail reader build failed')
    old = lab / 'results/cas-divergence-analysis-20261028-01'
    dump = subprocess.run([str(out / 'reader'), str(old / 'embedded.air'), 'divergence_case'],
                          capture_output=True, env=env, timeout=30)
    (out / 'read.stderr').write_bytes(dump.stderr)
    if dump.returncode != 0: raise ValueError('detail AIR reader failed')
    detail = out / 'typed-detail.json'; detail.write_bytes(dump.stdout)
    if sha(detail) != '57e0da2e7c19577a67258fa6a087d7276439e580f4d5ed1fac23b45194b09065':
        raise ValueError('detail dump differs')
    cfg = out / 'cfg/typed-cfg.json'; previous = old / 'typed-air.json'
    result = inspect(json.loads(detail.read_bytes()), json.loads(cfg.read_bytes()),
                     json.loads(previous.read_bytes()), 'divergence_case')
    fields = ('alloca_instruction', 'cast_instruction', 'cast_subcode', 'lifetime_start_instruction',
              'initial_store_instruction', 'CAS_instruction', 'expected_load_instruction',
              'lifetime_end_instruction', 'direct_pointer_uses', 'cast_pointer_uses', 'output_component')
    if tuple(result[k] for k in fields) != (0, 46, 11, 47, 48, 49, 51, 52, 4, 2, 0):
        raise ValueError('pointer observation differs')
    result.update({'GPU_dispatches':0, 'detail_sha256':sha(detail), 'cfg_sha256':sha(cfg),
                   'reader_sha256':sha(out/'reader'), 'reader_source_sha256':sha(source),
                   'inspector_sha256':sha(Path(__file__).with_name('inspect_cas_pointer.py')),
                   'reproducer_sha256':sha(Path(__file__))})
    with (out/'pointer-observation.json').open('x') as f:
        json.dump(result, f, indent=2, sort_keys=True); f.write('\n')
    print(json.dumps(result))


if __name__ == '__main__': main()
