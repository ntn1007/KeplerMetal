"""Synthetic packet/QMD counterexamples, never submitted to a GPU."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/experiments/cas_divergence'))
from audit_cb0 import inspect

def fixture():
    variant=bytearray(128);qmd=bytearray(256);code=0xfe001fe000;size=1344
    struct.pack_into('<Q',variant,16,code);struct.pack_into('<Q',variant,24,size);struct.pack_into('<I',variant,48,13)
    struct.pack_into('<I',qmd,0x50,7);address=code+((size+255)&~255)
    struct.pack_into('<I',qmd,0x74,address&0xffffffff)
    struct.pack_into('<I',qmd,0x78,((address>>32)&255)|(256<<15))
    struct.pack_into('<I',qmd,0x20,code&0xffffffff);struct.pack_into('<I',qmd,0xb8,13<<24)
    header=(3<<29)|(64<<16)|(1<<13)|(0x1b4//4)
    return bytearray(struct.pack('<I',header)+qmd),variant

class CB0Observation(unittest.TestCase):
    def test_observed_shape(self):
        cmd,v=fixture();r=inspect(bytes(cmd),bytes(v),'native')
        self.assertTrue(r['CB0_equals_code_end_aligned_256']);self.assertEqual(r['CB0_bytes'],256)

    def test_wrong_bank_range_code_and_registers_rejected(self):
        for offset in (0x50,0x74,0x78,0x20,0xbb):
            cmd,v=fixture();cmd[4+offset]^=1
            with self.subTest(offset=offset),self.assertRaises(ValueError):inspect(bytes(cmd),bytes(v),'native')
        cmd,v=fixture();v[24]^=1
        with self.assertRaises(ValueError):inspect(bytes(cmd),bytes(v),'native')

    def test_truncated_duplicate_and_wrong_mode_rejected(self):
        cmd,v=fixture()
        for bad,mode in ((cmd[:-4],'native'),(cmd+cmd,'native'),(cmd,'repaired')):
            with self.assertRaises(ValueError):inspect(bytes(bad),bytes(v),mode)

if __name__=='__main__':unittest.main()
