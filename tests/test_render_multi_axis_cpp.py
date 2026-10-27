# SPDX-License-Identifier: MIT
import subprocess
import tempfile
from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class MultiAxisPlan(unittest.TestCase):
 def test_two_slots_eight_states_all_selector_orders(self):
  with tempfile.TemporaryDirectory() as tmp:
   exe=Path(tmp)/'multi-axis'
   subprocess.run(['clang++','-std=c++17','-O2','-I',str(ROOT/'bridge/src'),str(ROOT/'tests/render_multi_axis_plan_test.cpp'),'-o',str(exe)],check=True)
   r=subprocess.run([str(exe)],check=True,capture_output=True,text=True)
   self.assertIn('MULTI_AXIS_PLAN_PASS',r.stdout)
