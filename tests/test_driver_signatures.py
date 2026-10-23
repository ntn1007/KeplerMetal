"""Synthetic container tests; no proprietary executable or GPU is used."""
import importlib.util
from pathlib import Path
import struct
import unittest

spec=importlib.util.spec_from_file_location('signature_compare',Path(__file__).resolve().parents[1]/'tools/compare_driver_signatures.py')
tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)


def fixture():
    cd=struct.pack('>II',0xfade0c02,12)+b'CODE'
    cms=struct.pack('>II',0xfade0b01,24)+b'A'*16
    sig=struct.pack('>III',0xfade0cc0,28+len(cd)+len(cms),2)+struct.pack('>IIII',0,28,0x10000,28+len(cd))+cd+cms
    head=struct.pack('<8I',0xfeedfacf,0x1000007,3,6,1,16,0,0)+struct.pack('<4I',0x1d,16,128,len(sig))
    return head+b'X'*(128-len(head))+sig


class DriverSignatureTests(unittest.TestCase):
    def test_identical(self):
        self.assertEqual(tool.compare(fixture(),fixture())['classification'],'IDENTICAL')

    def test_cms_only(self):
        a=fixture();b=a[:-1]+b'B';r=tool.compare(a,b)
        self.assertEqual(r['classification'],'CMS_SIGNATURE_ONLY')
        self.assertEqual(r['different_bytes'],1)
        self.assertTrue(r['outside_signature_identical'] and r['CodeDirectory_identical'])
        self.assertFalse(r['runtime_compatibility_proved'])

    def test_program_change(self):
        a=fixture();b=bytearray(a);b[90]^=1
        self.assertEqual(tool.compare(a,bytes(b))['classification'],'CONTENT_CHANGED')

    def test_code_directory_change(self):
        a=fixture();b=bytearray(a);b[128+28+8]^=1
        self.assertEqual(tool.compare(a,bytes(b))['classification'],'CONTENT_CHANGED')

    def test_invalid_containers_rejected(self):
        for offset,fmt,value in [(0,'<I',0),(4,'<I',7),(16,'<I',4097),(20,'<I',0xffffffff),
                (36,'<I',0),(40,'<I',16),(44,'<I',0xffffffff),
                (128,'>I',0),(132,'>I',0xffffffff),(136,'>I',65),
                (144,'>I',1),(148,'>I',0),(152,'>I',28),(128+28+4,'>I',0xffffffff)]:
            with self.subTest(offset=offset,value=value):
                a=bytearray(fixture());struct.pack_into(fmt,a,offset,value)
                with self.assertRaises(ValueError):tool.signature(bytes(a))

    def test_truncated(self):
        for end in [0,31,40,127,len(fixture())-1]:
            with self.subTest(end=end),self.assertRaises(ValueError):tool.signature(fixture()[:end])


if __name__=='__main__':unittest.main()
