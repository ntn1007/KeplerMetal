# SPDX-License-Identifier: MIT
"""Synthetic Mach-O validation of bounded signature-layout comparison."""
import importlib.util
from pathlib import Path
import struct
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
spec=importlib.util.spec_from_file_location('signing_layout',ROOT/'tools/compare_signing_layout.py')
tool=importlib.util.module_from_spec(spec);spec.loader.exec_module(tool)


def fixture(cms_payload=b'A'*16):
    cd=struct.pack('>II',0xfade0c02,12)+b'CODE'
    cms=struct.pack('>II',0xfade0b01,8+len(cms_payload))+cms_payload
    sig=struct.pack('>III',0xfade0cc0,28+len(cd)+len(cms),2)+struct.pack('>IIII',0,28,0x10000,28+len(cd))+cd+cms
    start=192;fileoff=160;total=start+len(sig)
    head=struct.pack('<8I',0xfeedfacf,0x1000007,3,6,2,88,0,0)
    seg=bytearray(72);struct.pack_into('<II',seg,0,0x19,72);seg[8:18]=b'__LINKEDIT'
    struct.pack_into('<QQQQ',seg,24,0x1000,4096,fileoff,total-fileoff)
    cmd=struct.pack('<4I',0x1d,16,start,len(sig))
    return head+bytes(seg)+cmd+b'X'*(start-len(head)-len(seg)-len(cmd))+sig


class SigningLayoutTests(unittest.TestCase):
    def test_differing_signature_size_and_payload(self):
        r=tool.compare(fixture(),fixture(b'B'*24))
        self.assertEqual(r['classification'],'SAME_PRE_SIGNATURE_EXCEPT_VALIDATED_SIZE_FIELDS')
        self.assertTrue(r['normalized_pre_signature_equal'])
        self.assertEqual(r['raw_pre_signature_different_bytes'],2)
        self.assertFalse(r['runtime_compatibility_proved'])

    def test_code_difference_is_not_hidden(self):
        a=fixture();b=bytearray(fixture(b'B'*24));b[150]^=1
        self.assertEqual(tool.compare(a,bytes(b))['classification'],'OTHER_PRE_SIGNATURE_DIFFERENCES')

    def test_linkedit_size_is_validated_not_blindly_ignored(self):
        bad=bytearray(fixture());struct.pack_into('<Q',bad,32+48,123)
        with self.assertRaisesRegex(ValueError,'terminate'):tool.compare(fixture(),bytes(bad))

    def test_trailing_bytes_are_refused(self):
        with self.assertRaisesRegex(ValueError,'terminate'):tool.compare(fixture(),fixture()+b'extra')

    def test_corrupt_signature_is_refused(self):
        bad=bytearray(fixture());struct.pack_into('>I',bad,192,0)
        with self.assertRaises(ValueError):tool.compare(fixture(),bytes(bad))

    def test_different_valid_signature_offset_is_not_comparable(self):
        a=fixture();b=bytearray(fixture());b[192:192]=b'\0'*8
        struct.pack_into('<I',b,32+72+8,200)
        struct.pack_into('<Q',b,32+48,len(b)-160)
        self.assertEqual(tool.compare(a,bytes(b))['classification'],'LAYOUT_NOT_COMPARABLE')

if __name__=='__main__':unittest.main()
