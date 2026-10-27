# SPDX-License-Identifier: MIT
import importlib.util,struct,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bridge/tools'))
spec=importlib.util.spec_from_file_location('buffer_user_contract',ROOT/'bridge/tools/video_buffer_user_contract.py')
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)

class DirectBranchTests(unittest.TestCase):
    def test_forward_and_backward_targets(self):
        start=0x1000
        self.assertEqual(mod.branch(b'\xe8'+struct.pack('<i',0x20),start,start,0xe8),0x1025)
        self.assertEqual(mod.branch(b'\xe9'+struct.pack('<i',-0x10),start,start,0xe9),0xff5)
    def test_rejects_wrong_opcode_and_bounds(self):
        with self.assertRaises(ValueError):mod.branch(b'\xe9'+b'\0'*4,0x1000,0x1000,0xe8)
        with self.assertRaises(ValueError):mod.branch(b'\xe8'+b'\0'*3,0x1000,0x1000,0xe8)
        with self.assertRaises(ValueError):mod.branch(b'\xe8'+b'\0'*4,0x1000,0x0fff,0xe8)

if __name__=='__main__':unittest.main()
