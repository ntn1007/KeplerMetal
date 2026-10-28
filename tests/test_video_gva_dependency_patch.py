# SPDX-License-Identifier: MIT
import importlib.util,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('dependency_patch',ROOT/'bridge/experiments/video_gva_support_overlay/dependency_patch.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class DependencyPatchTests(unittest.TestCase):
 def test_extended_observation_keeps_substitution_at_original_site(self):
  source=(ROOT/'bridge/tools/video_dependency.mm').read_text();patched=mod.apply(source)
  self.assertIn('caller==nativeSite||gva',patched)
  self.assertIn('!synthetic&&caller==nativeSite,',patched)
  self.assertIn('event.gva=gva',patched)
 def test_source_drift_refused(self):
  source=(ROOT/'bridge/tools/video_dependency.mm').read_text();damaged=source.replace('event.control=synthetic;event.caller=caller;','event.control=synthetic;',1)
  with self.assertRaises(ValueError):mod.apply(damaged)
if __name__=='__main__':unittest.main()
