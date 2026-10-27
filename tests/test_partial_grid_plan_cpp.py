# SPDX-License-Identifier: MIT
"""Exercise the actual bounded C++ planner against an independent thread set."""
import platform
import subprocess
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
class PartialGridPlanCPPTests(unittest.TestCase):
 @unittest.skipUnless(platform.system()=='Darwin','requires Xcode C++ compiler')
 def test_actual_planner_coverage_and_limits(self):
  with tempfile.TemporaryDirectory() as d:
   exe=Path(d)/'contract';subprocess.run(['xcrun','clang++','-std=c++17','-O2','-I',str(ROOT/'bridge/src'),str(ROOT/'tests/partial_grid_plan_contract.cpp'),'-o',str(exe)],check=True,capture_output=True,text=True,timeout=60)
   subprocess.run([str(exe)],check=True,capture_output=True,text=True,timeout=30)
