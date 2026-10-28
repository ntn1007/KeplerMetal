"""Compile and run the real conditional auxiliary gate on the CPU."""
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ConditionalAux(unittest.TestCase):
    def test_digest_and_mismatch_refusals(self):
        env = {k:v for k,v in os.environ.items() if not k.startswith(('DYLD_', 'LD_'))}
        with tempfile.TemporaryDirectory(prefix='kepler-aux-test-') as tmp:
            exe = Path(tmp) / 'guard-test'
            built = subprocess.run(['clang++', '-std=c++17', '-I', str(ROOT/'bridge/src'),
                                    str(ROOT/'tests/conditional_aux_guard.cpp'), '-o', str(exe)],
                                   capture_output=True, text=True, env=env, timeout=60)
            self.assertEqual(built.returncode, 0, built.stderr)
            run = subprocess.run([str(exe)], capture_output=True, text=True, env=env, timeout=30)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn('12 byte mutations', run.stdout)


if __name__ == '__main__': unittest.main()
