# SPDX-License-Identifier: MIT
"""Compile and exercise the offline planner; this is not a GPU test."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class PipelineTransitionPlanner(unittest.TestCase):
    def test_compiled_planner_contract(self):
        compiler = shutil.which('clang++') or shutil.which('g++')
        if not compiler:
            self.skipTest('No C++ compiler available')
        with tempfile.TemporaryDirectory(prefix='kepler-pipeline-test-') as directory:
            binary = Path(directory) / 'planner-test'
            result = subprocess.run([compiler, '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror',
                '-I', str(ROOT/'bridge/src'), str(ROOT/'tests/pipeline_transition_plan_test.cpp'), '-o', str(binary)],
                capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), 'PIPELINE_TRANSITION_PLANNER_PASS')
