# SPDX-License-Identifier: MIT
"""Bounded compressed/raw payload identity controls."""
import hashlib
import importlib.util
import io
import lzma
import struct
import unittest
from pathlib import Path

path = Path(__file__).resolve().parents[1]/'bridge/experiments/video_gva_archive_survey/payload_identity.py'
spec = importlib.util.spec_from_file_location('payload_identity',path)
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)


def chunk(flags, data): return struct.pack('>QQ',flags,len(data))+data


class PayloadIdentityTest(unittest.TestCase):
    def test_raw_and_xz_and_exact_digest(self):
        raw=b'raw data'; plain=b'compressed data'*100
        payload=b'pbzx'+struct.pack('>Q',0x1000000)+chunk(0x1000000,raw)+chunk(0,lzma.compress(plain))
        r=module.verify(io.BytesIO(payload),hashlib.sha256(raw+plain).hexdigest(),len(raw+plain))
        self.assertEqual(r['chunks'],2)
        self.assertEqual(r['compressed_sha256'],hashlib.sha256(payload).hexdigest())
        with self.assertRaisesRegex(ValueError,'does not match'):
            module.verify(io.BytesIO(payload),'0'*64,len(raw+plain))
        with self.assertRaisesRegex(ValueError,'trailing'):
            module.verify(io.BytesIO(payload+b'x'),hashlib.sha256(raw+plain).hexdigest(),len(raw+plain))

    def test_truncated(self):
        payload=b'pbzx'+struct.pack('>Q',0x1000000)+struct.pack('>QQ',0,10)+b'bad'
        with self.assertRaisesRegex(ValueError,'truncated'):
            module.verify(io.BytesIO(payload),'0'*64,0)


if __name__ == '__main__': unittest.main()
