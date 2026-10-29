# SPDX-License-Identifier: MIT
"""Malformed-container checks for the read-only historical audit."""
import importlib.util
from pathlib import Path
import struct
import unittest

p=Path(__file__).resolve().parents[1]/'bridge/experiments/video_gva_historical_classification/audit.py'
spec=importlib.util.spec_from_file_location('historical_gva_audit',p)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def container(entries,payload=b'hello'):
    start=8+20*len(entries)
    return b'\xca\xfe\xba\xbe'+struct.pack('>I',len(entries))+b''.join(struct.pack('>IIIII',cpu,0,start,size,0) for cpu,size in entries)+payload

class FatSliceTest(unittest.TestCase):
    def test_exact_x86_slice(self):
        self.assertEqual(m.fat_x86(container([(0x01000007,5)])),b'hello')
    def test_rejects_truncated_missing_and_ambiguous(self):
        for value in (b'',container([(0x01000007,6)]),container([(7,5)]),container([(0x01000007,5),(0x01000007,5)])):
            with self.assertRaises(ValueError):m.fat_x86(value)
    def test_rejects_bad_macho_header(self):
        with self.assertRaises(ValueError):m.macho_profile(b'not a Mach-O')

if __name__=='__main__':unittest.main()
