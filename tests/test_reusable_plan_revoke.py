# SPDX-License-Identifier: MIT
import importlib.util, sys, unittest
from pathlib import Path
root=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('plan_revoke',root/'bridge/experiments/reusable_plan_revoke/experiment.py')
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)

class PlanWitnessSourceTests(unittest.TestCase):
 def test_transformation_is_pinned_to_unique_anchors(self):
  source=(root/'bridge/tools/command_ir_dataflow_client.mm').read_text();derived=e.transform(source)
  self.assertEqual(derived.count('#include "plan_probe.inc"'),1)
  self.assertIn('witness_after_restore',derived)
  for anchor in ('struct Push{',' BOOL reuseEncoder=',' if(scope)[scope restore];'):
   with self.assertRaises(ValueError):e.transform(source.replace(anchor,'',1))
   with self.assertRaises(ValueError):e.transform(source+anchor)

if __name__=='__main__':unittest.main()
