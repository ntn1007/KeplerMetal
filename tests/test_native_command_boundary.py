"""Portable malformed-capture controls; synthetic bytes never reach a GPU."""
from pathlib import Path
import struct
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'bridge/tools'))
from verify_native_command_boundary import parse_native_payload,classify


def payload(parts=None):
    if parts is None:parts=[(1,struct.pack('<I',5)),(0x10004,bytes(232)),(0x10005,bytes(64))]
    data=bytearray(struct.pack('<2I',7,0))
    for i,(kind,part)in enumerate(parts):
        data.extend(struct.pack('<QII',16+len(part)if i+1<len(parts)else 0,kind,len(part)));data.extend(part)
    struct.pack_into('<I',data,4,len(data));return data


class NativeCommandBoundary(unittest.TestCase):
    def rejected(self,data):
        with self.assertRaises(AssertionError):parse_native_payload(data)

    def test_complete_synthetic_capture(self):
        code,metadata=parse_native_payload(payload());self.assertEqual(code,bytes(64));self.assertEqual(metadata,[0]*58)

    def test_truncated_capture(self):self.rejected(payload()[:-1])
    def test_wrong_total(self):
        data=payload();struct.pack_into('<I',data,4,0);self.rejected(data)

    def test_unsupported_container_version(self):
        data=payload();struct.pack_into('<I',data,0,99);self.rejected(data)

    def test_section_size_overflow(self):
        data=payload();struct.pack_into('<I',data,20,0xffffffff);self.rejected(data)

    def test_nonforward_section_link(self):
        data=payload();struct.pack_into('<Q',data,8,4);self.rejected(data)

    def test_early_termination_cannot_hide_bytes(self):
        data=payload();struct.pack_into('<Q',data,8,0);self.rejected(data)

    def test_duplicate_code_section(self):
        self.rejected(payload([(1,struct.pack('<I',5)),(0x10004,bytes(232)),(0x10005,bytes(64)),(0x10005,bytes(64))]))

    def test_missing_metadata(self):self.rejected(payload([(1,struct.pack('<I',5)),(0x10005,bytes(64))]))
    def test_wrong_stage(self):self.rejected(payload([(1,struct.pack('<I',6)),(0x10004,bytes(232)),(0x10005,bytes(64))]))
    def test_unaligned_or_empty_code(self):
        for size in [0,63,65]:self.rejected(payload([(1,struct.pack('<I',5)),(0x10004,bytes(232)),(0x10005,bytes(size))]))

    def test_unrelated_refusal_not_classified_as_command_metadata(self):
        self.assertEqual(classify(dict(outcome='PIPELINE_REFUSED',pipeline_error='file missing')),'unclassified_pipeline_refusal')
        self.assertEqual(classify(dict(outcome='PIPELINE_REFUSED',pipeline_error='Unsupported indirect argument kind "air.command_buffer"')),'command_argument_metadata_refused')

    def test_pipeline_creation_never_claims_execution(self):
        self.assertEqual(classify(dict(outcome='PIPELINE_CREATED_NOT_EXECUTED')),'pipeline_created_not_executed')


if __name__=='__main__':unittest.main()
