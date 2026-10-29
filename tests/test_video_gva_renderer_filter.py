# SPDX-License-Identifier: MIT
"""Boundary checks for the offline model; never dispatch these inputs."""
import importlib.util
from pathlib import Path
import unittest

PATH=Path(__file__).resolve().parents[1]/'bridge/experiments/video_gva_renderer_filter/audit.py'
spec=importlib.util.spec_from_file_location('renderer_filter_audit',PATH)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


class RendererFilterTest(unittest.TestCase):
    def test_complete_first_mask_and_neighbours(self):
        accepted={0,1,3,7,15,31}
        for index in range(32):
            self.assertEqual(module.classify(0x1080001+index),'first' if index in accepted else 'excluded')
        self.assertEqual(module.classify(0x1080000),'excluded')
        self.assertEqual(module.classify(0x1080021),'excluded')
        self.assertEqual(module.classify(0x1080080),'first')
    def test_complete_second_mask_and_neighbours(self):
        for index in range(5):
            self.assertEqual(module.classify(0x1020000+index),'second' if index in {0,2,4} else 'excluded')
        self.assertEqual(module.classify(0x101ffff),'excluded')
        self.assertEqual(module.classify(0x1020005),'excluded')
    def test_observed_and_unsigned_range(self):
        self.assertEqual(module.classify(0x1040008),'excluded')
        self.assertEqual(module.classify(0xffffffff),'excluded')
        for value in (-1,0x100000000,'bad'):
            with self.assertRaises(ValueError):module.classify(value)

if __name__=='__main__':unittest.main()
