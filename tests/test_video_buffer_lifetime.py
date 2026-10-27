# SPDX-License-Identifier: MIT
import importlib.util,struct,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'bridge/tools'))
spec=importlib.util.spec_from_file_location('video_buffer_lifetime',ROOT/'bridge/tools/video_buffer_lifetime.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class RipLeaTests(unittest.TestCase):
    def test_relative_address_both_directions(self):
        self.assertEqual(mod.rip_lea(b'\x48\x8d\x3d'+struct.pack('<i',0x20),0x1000,0x1000),0x1027)
        self.assertEqual(mod.rip_lea(b'\x48\x8d\x3d'+struct.pack('<i',-0x10),0x1000,0x1000),0xff7)
    def test_wrong_encoding_or_truncation_rejected(self):
        for data,site in [(b'\x48\x8d\x35'+b'\0'*4,0x1000),(b'\x48\x8d\x3d'+b'\0'*3,0x1000),(b'\x48\x8d\x3d'+b'\0'*4,0xfff)]:
            with self.subTest(data=data,site=site),self.assertRaises(ValueError):mod.rip_lea(data,0x1000,site)
if __name__=='__main__':unittest.main()
