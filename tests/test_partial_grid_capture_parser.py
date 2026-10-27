# SPDX-License-Identifier: MIT
"""Only synthetic bytes are parsed; no malformed data reaches a driver."""
import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge/tools'))
from partial_grid_capture import extract


def section(kind, data, step=0):
    return struct.pack('<QII', step, kind, len(data)) + data


def container(*sections):
    payload = b''.join(sections)
    return struct.pack('<II', 8, len(payload) + 8) + payload


class CaptureParserTests(unittest.TestCase):
    def test_complete_container(self):
        code = bytes(range(64))
        self.assertEqual(extract(container(section(0x10004, bytes(232), 248), section(0x10005, code))), code)

    def test_bad_containers_refused(self):
        meta = section(0x10004, bytes(232), 248)
        code = section(0x10005, bytes(64))
        valid = container(meta, code)
        bad = [valid[:-1], struct.pack('<II', 99, len(valid)) + valid[8:],
               container(section(0x10004, bytes(231), 247), code),
               container(section(0x10004, bytes(232), 16), code),
               container(meta, section(0x10005, bytes(63))),
               container(section(0x10004, bytes(232), 248),
                         section(0x10004, bytes(232), 248), code),
               container(meta), container(section(0x10005, bytes(64)))]
        for sample in bad:
            with self.subTest(length=len(sample)):
                with self.assertRaises(ValueError):
                    extract(sample)
