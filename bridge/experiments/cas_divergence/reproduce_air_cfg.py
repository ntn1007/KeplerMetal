#!/usr/bin/env python3
"""Rebuild and inspect the retained conditional CAS AIR, without GPU work."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from inspect_air_cfg import inspect


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--lab', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args(); lab = a.lab.resolve(); out = a.out.resolve()
    out.relative_to(lab / 'results')
    if out.exists() or not out.parent.is_dir():
        raise ValueError('fresh output directory required')
    old = lab / 'results/cas-divergence-analysis-20261028-01'
    vendor = lab / 'vendor/OpenNVDA-da0c53d0a2a0b69b658c9e26b4cfa51946fff5f5/drivers/NVMTLDriver/air'
    inputs = {
        old / 'embedded.air': '57f48fd3bc747c45b1a0d2b82fddea4c4bab97f18042e4d70afe5086fbaedc0b',
        old / 'typed-air.json': '45c91be0e401de5272c47c38bf31c8fec5ff05f8d885a731ae60be04fe29b1ad',
        vendor / 'airir.h': '7360af64f27d3bc0c63ceffb83926a36daafc26c59d9379882a57204585d6d84',
        lab / 'build/air-bitstream.o': 'e98b276a537ea8bdf247dde2ef04ada35ec8e588fc15bc45a2d2b1d3731ece5e',
        lab / 'build/air-airir.o': '473b8e25bb10ec9786616bbb74d7892d98c4d1b90e09838d93022a2fdce0b75e',
    }
    if any(sha(path) != digest for path, digest in inputs.items()):
        raise ValueError('retained input fingerprint differs')
    source = Path(__file__).with_name('cfg_air_dump.c')
    out.mkdir()
    env = {k: v for k, v in os.environ.items() if not k.startswith(('DYLD_', 'LD_'))}
    command = ['clang', '-O2', '-I' + str(vendor), str(source), str(lab / 'build/air-bitstream.o'),
               str(lab / 'build/air-airir.o'), '-o', str(out / 'reader')]
    built = subprocess.run(command, capture_output=True, env=env, timeout=60)
    (out / 'build.stderr').write_bytes(built.stderr)
    if built.returncode != 0:
        raise ValueError('AIR reader build failed')
    read = subprocess.run([str(out / 'reader'), str(old / 'embedded.air'), 'divergence_case'],
                          capture_output=True, env=env, timeout=30)
    (out / 'read.stderr').write_bytes(read.stderr)
    if read.returncode != 0:
        raise ValueError('AIR reader failed')
    (out / 'typed-cfg.json').write_bytes(read.stdout)
    result = inspect(json.loads(read.stdout), json.loads((old / 'typed-air.json').read_bytes()), 'divergence_case')
    expected = (12, 19, 49, 51, 48, 55, 9, 8, 7, 61, 0)
    actual = tuple(result[k] for k in ('blocks', 'edges', 'CAS_instruction', 'expected_load_instruction',
                 'initial_store_instruction', 'phi_instruction', 'phi_block', 'CAS_block', 'fallback_block',
                 'vector_insertion_instruction', 'inserted_component'))
    if actual != expected or any(sha(path) != digest for path, digest in inputs.items()):
        raise ValueError('observation or retained input changed')
    result.update({'GPU_dispatches': 0, 'AIR_sha256': inputs[old / 'embedded.air'],
                   'typed_CFG_sha256': sha(out / 'typed-cfg.json'), 'reader_source_sha256': sha(source),
                   'inspector_sha256': sha(Path(__file__).with_name('inspect_air_cfg.py')),
                   'reproducer_sha256': sha(Path(__file__)),
                   'reader_binary_sha256': sha(out / 'reader'),
                   'previous_typed_sha256': inputs[old / 'typed-air.json'],
                   'reader_object_sha256': [inputs[lab / 'build/air-bitstream.o'], inputs[lab / 'build/air-airir.o']]})
    with (out / 'observation.json').open('x') as stream:
        json.dump(result, stream, indent=2, sort_keys=True); stream.write('\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
