# SPDX-License-Identifier: MIT
"""Offline checks for the captured constructor-section audit."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge/tools'))
from audit_cas_sdk_qualification import captured_sections

def section(next_delta, kind, data):
    return struct.pack('<QII', next_delta, kind, len(data)) + data

class CapturedSections(unittest.TestCase):
    def test_relative_link_extracts_exact_payloads(self):
        blob = b'\0' * 8 + section(24, 0x10004, b'metadata') + section(0, 0x10005, b'code')
        self.assertEqual(captured_sections(blob), {0x10004:b'metadata', 0x10005:b'code'})

    def test_duplicate_or_truncated_sections_are_refused(self):
        duplicate = b'\0' * 8 + section(24, 0x10004, b'metadata') + section(0, 0x10004, b'code')
        truncated = b'\0' * 8 + struct.pack('<QII', 0, 0x10004, 100) + b'x'
        for blob in (duplicate, truncated):
            with self.subTest(size=len(blob)), self.assertRaises(ValueError):
                captured_sections(blob)

if __name__=='__main__': unittest.main()
