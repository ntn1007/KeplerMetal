# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path
import unittest

p=Path(__file__).resolve().parents[1]/'bridge/experiments/video_selector_translation_guard/audit.py'
spec=importlib.util.spec_from_file_location('selector_guard',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

class SelectorGuardTest(unittest.TestCase):
    def test_same_shape_does_not_authorize(self):
        old={'selector':'0x101','function_name':'set_source_size','flags':4,'count0':0,'count1':0xffffffff}
        new={'selector':1,'method_symbol':'set_client_info','flags':4,'count0':0,'count1':0xffffffff,'member_pointer_kind':'direct'}
        r=m.assess(old,new);self.assertTrue(r['same_shape']);self.assertFalse(r['mapping_authorized']);self.assertEqual(r['decision'],'REJECT_UNQUALIFIED')
    def test_channel_count_mismatch_refused(self):
        old={'selector':'0x105','function_name':'acquire_channel','flags':0,'count0':1,'count1':2}
        new={'selector':5,'method_symbol':'finish_fence_event','flags':0,'count0':1,'count1':0,'member_pointer_kind':'direct'}
        r=m.assess(old,new);self.assertFalse(r['same_shape']);self.assertFalse(r['mapping_authorized'])
    def test_unrelated_index_rejected(self):
        with self.assertRaises(ValueError):m.assess({'selector':'0x105'},{'selector':4})

if __name__=='__main__':unittest.main()
