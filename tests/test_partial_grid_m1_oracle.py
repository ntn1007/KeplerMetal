# SPDX-License-Identifier: MIT
"""Exercise the independent CPU oracle with synthetic, rehashed corruption."""
import hashlib
import json
import math
import struct
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge/tools'))
from verify_partial_grid_m1 import verify


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    data = json.dumps(value).encode()
    path.write_bytes(data)
    return digest(data)


def create_fixture(root):
    for name in ('reference.mm', 'reference', 'runner.py'):
        (root / name).write_bytes(name.encode())
    cohort = root / 'qualified-01'
    cohort.mkdir()
    records = []
    for pid, mode in enumerate(('negative3d', 'partial1d', 'partial3d'), 1):
        d = cohort / mode
        d.mkdir()
        grid = (33, 1, 1) if mode == 'partial1d' else (11, 7, 5)
        nominal = (32, 1, 1) if mode == 'partial1d' else (4, 4, 3)
        n = math.prod(grid)
        raw = bytearray(b'\xa5' * (128 * n + 128))
        groups = tuple((g + l - 1) // l for g, l in zip(grid, nominal))
        if mode != 'negative3d':
            for z in range(grid[2]):
                for y in range(grid[1]):
                    for x in range(grid[0]):
                        gid = (x, y, z)
                        index = x + grid[0] * (y + grid[1] * z)
                        group = tuple(g // l for g, l in zip(gid, nominal))
                        lane = tuple(g % l for g, l in zip(gid, nominal))
                        local = tuple(min(l, g - b*l) for g, l, b in zip(grid, nominal, group))
                        linear = lane[0] + local[0]*(lane[1] + local[1]*lane[2])
                        row = (*gid, index, *lane, linear, *group, 0, *groups, 0, *local, 0,
                               *nominal, 0, *grid, 0, math.prod(local), 0, 0, 0)
                        struct.pack_into('<32I', raw, 64 + 128 * index, *row)
        (d / 'output.bin').write_bytes(raw)
        positive = mode != 'negative3d'
        result = {'mode': mode, 'pid': pid, 'uid': 501, 'euid': 501,
                  'device': 'Apple M1 Max', 'registry_id': 1, 'supports_apple4': True,
                  'threadgroup_barrier_used': True, 'grid': list(grid), 'dispatch_local': list(nominal),
                  'elements': n, 'guard': 64, 'output_bytes': len(raw), 'submitted': positive,
                  'command_status': 4 if positive else 0, 'counter': n if positive else 0}
        records.append({'mode': mode, 'pid': pid, 'exit_code': 0, 'kill_requested': False,
                        'elapsed_monotonic_ns': 1, 'started_at': f'2026-01-01T00:00:0{pid}',
                        'completed_at': f'2026-01-01T00:00:0{pid}',
                        'result_SHA256': write_json(d / 'result.json', result), 'output_SHA256': digest(raw)})
    sha = lambda name: digest((root / name).read_bytes())
    manifest = {'status': 'PASS', 'architecture': 'arm64', 'user_UID': 501, 'system_modified': False,
                'source_SHA256': sha('reference.mm'), 'binary_SHA256': sha('reference'),
                'runner_SHA256': sha('runner.py'), 'after': {'source_SHA256': sha('reference.mm'),
                'binary_SHA256': sha('reference')}, 'records': records, 'macOS': 'test',
                'macOS_build': 'test', 'SDK': 'test'}
    write_json(cohort / 'manifest.json', manifest)
    return cohort, manifest


class M1OracleTests(unittest.TestCase):
    def test_synthetic_and_rehashed_corruption(self):
        with tempfile.TemporaryDirectory() as tmp, patch('verify_partial_grid_m1.subprocess.run'):
            root = Path(tmp)
            cohort, manifest = create_fixture(root)
            self.assertEqual(verify(root)['positive_threads'], 418)
            p = cohort / 'partial3d' / 'output.bin'
            raw = bytearray(p.read_bytes())
            raw[64 + 16] ^= 1  # local thread x, with a valid recomputed hash
            p.write_bytes(raw)
            manifest['records'][2]['output_SHA256'] = digest(raw)
            write_json(cohort / 'manifest.json', manifest)
            with self.assertRaises(AssertionError):
                verify(root)

    def test_negative_control_and_status_must_hold(self):
        with tempfile.TemporaryDirectory() as tmp, patch('verify_partial_grid_m1.subprocess.run'):
            root = Path(tmp)
            cohort, manifest = create_fixture(root)
            p = cohort / 'negative3d' / 'output.bin'
            raw = bytearray(p.read_bytes())
            raw[100] = 0
            p.write_bytes(raw)
            manifest['records'][0]['output_SHA256'] = digest(raw)
            write_json(cohort / 'manifest.json', manifest)
            with self.assertRaises(AssertionError):
                verify(root)
            p.write_bytes(bytes([0xa5]) * len(raw))
            manifest['records'][0]['output_SHA256'] = digest(p.read_bytes())
            manifest['records'][1]['exit_code'] = 1
            write_json(cohort / 'manifest.json', manifest)
            with self.assertRaises(AssertionError):
                verify(root)
