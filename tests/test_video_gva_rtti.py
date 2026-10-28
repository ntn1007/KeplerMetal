"""Portable negative cases for the offline constructor address decoder."""
import importlib.util
import struct
import sys
import tempfile
import unittest
from pathlib import Path

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root/'bridge/tools'))
spec=importlib.util.spec_from_file_location('gva_rtti_audit',root/'bridge/experiments/video_gva_rtti/audit.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

class ConstructorDecoder(unittest.TestCase):
    def test_signed_relative_call_and_lea(self):
        call=b'\xe8'+struct.pack('<i',-20)
        self.assertEqual(module.branch(call,100,0,0xe8),85)
        instruction=b'\x48\x8d\x05'+struct.pack('<i',40)
        self.assertEqual(module.lea(instruction,100,0),147)

    def test_truncated_and_wrong_opcodes_refused(self):
        for data in (b'',b'\xe9\0\0\0',b'\xe8\0\0\0\0'):
            with self.subTest(data=data),self.assertRaises(ValueError):module.branch(data,10,0,0xe9)
        for data in (b'',b'\x48\x8d\x04\0\0\0\0'):
            with self.subTest(data=data),self.assertRaises(ValueError):module.lea(data,10,0)

    def test_malformed_analysis_container_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'fake.o'
            for data in (b'not-an-elf',b'\x7fELF\x02\x01'):
                p.write_bytes(data)
                with self.subTest(data=data),self.assertRaises(ValueError):module.verify_object(p,b'\0'*10,123)

if __name__=='__main__':unittest.main()
