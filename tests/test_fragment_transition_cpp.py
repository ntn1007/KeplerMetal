# SPDX-License-Identifier: MIT
"""Compile and exercise the fragment planner without Metal or a GPU."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class FragmentTransitionPlanner(unittest.TestCase):
    def test_compiled_planner_contract(self):
        compiler=shutil.which('clang++') or shutil.which('g++')
        if not compiler:self.skipTest('No C++ compiler available')
        with tempfile.TemporaryDirectory(prefix='kepler-fragment-test-') as directory:
            binary=Path(directory)/'planner-test'
            result=subprocess.run([compiler,'-std=c++17','-O2','-Wall','-Wextra','-Werror',
                '-I',str(ROOT/'bridge/src'),str(ROOT/'tests/fragment_transition_plan_test.cpp'),'-o',str(binary)],
                capture_output=True,text=True,timeout=60)
            self.assertEqual(result.returncode,0,result.stderr)
            result=subprocess.run([str(binary)],capture_output=True,text=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout.strip(),'FRAGMENT_TRANSITION_PLANNER_PASS')
