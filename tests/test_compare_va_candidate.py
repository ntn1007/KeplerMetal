# SPDX-License-Identifier: MIT
import hashlib
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge' / 'tools'))
from compare_va_candidate import find_direct_path, inspect_bytes, thin_x86, uleb_starts


def fixture():
    data = bytearray(0x400)
    commands = []
    segment = bytearray(72)
    struct.pack_into('<II16sQQQQiiII', segment, 0, 0x19, 72, b'__TEXT', 0, 0x300, 0, 0x300, 7, 5, 0, 0)
    commands.append(segment)
    commands.append(struct.pack('<IIIIII', 2, 24, 0x300, 1, 0x310, 32))
    commands.append(struct.pack('<IIII', 0x26, 16, 0x350, 4))
    commands.append(struct.pack('<II16s', 0x1b, 24, bytes(range(16))))
    raw = b''.join(commands)
    struct.pack_into('<IIIIIIII', data, 0, 0xfeedfacf, 0x1000007, 3, 6, len(commands), len(raw), 0, 0)
    data[32:32 + len(raw)] = raw
    data[0x200:0x20b] = bytes.fromhex('554889e5b80e0000005dc3')
    struct.pack_into('<IBBHQ', data, 0x300, 1, 0x0f, 1, 0, 0x200)
    name = b'\0_AVD_CreateAVDAccelerator\0'
    data[0x310:0x310 + len(name)] = name
    data[0x350:0x354] = b'\x80\x04\x0b\0'
    return bytes(data)


class CandidateParserTests(unittest.TestCase):
    def test_direct_path_handles_cycles_and_unreachable_calls(self):
        graph = {1: [(2, 101), (3, 102)], 2: [(1, 201)], 3: [(4, 301)]}
        self.assertEqual(find_direct_path(graph, 1, {4}), ([(1, 102, 3), (3, 301, 4)], 4))
        self.assertIsNone(find_direct_path(graph, 1, {9}))

    def test_symbol_range_and_stub_are_derived(self):
        raw = fixture()
        row = inspect_bytes(raw, '_AVD_CreateAVDAccelerator')
        self.assertEqual((row['function_start'], row['next_function_start'], row['function_bytes']), (0x200, 0x20b, 11))
        self.assertEqual(row['function_SHA256'], hashlib.sha256(raw[0x200:0x20b]).hexdigest())
        self.assertTrue(row['exact_known_return_14_stub'])

    def test_fat_slice_and_invalid_ranges(self):
        raw = fixture()
        fat = struct.pack('>II', 0xcafebabe, 1) + struct.pack('>IIIII', 0x1000007, 3, 0x100, len(raw), 0)
        fat += b'\0' * (0x100 - len(fat)) + raw
        self.assertEqual(thin_x86(fat), raw)
        with self.assertRaises(ValueError):
            thin_x86(fat[:-1])
        with self.assertRaises(ValueError):
            thin_x86(struct.pack('>II', 0xcafebabe, 0))

    def test_truncated_and_unterminated_function_table_refused(self):
        with self.assertRaises(ValueError):
            uleb_starts(b'\x80', 0, 1, 0)
        with self.assertRaises(ValueError):
            uleb_starts(b'\x01', 0, 1, 0)
        raw = bytearray(fixture()); raw[0x350:0x354] = b'\x80\x80\x80\x80'
        with self.assertRaises(ValueError):
            inspect_bytes(bytes(raw), '_AVD_CreateAVDAccelerator')

    def test_missing_export_and_bad_string_refused(self):
        with self.assertRaises(ValueError):
            inspect_bytes(fixture(), '_unknown')
        raw = bytearray(fixture()); struct.pack_into('<I', raw, 0x300, 33)
        with self.assertRaises(ValueError):
            inspect_bytes(bytes(raw), '_AVD_CreateAVDAccelerator')

    def test_duplicate_uuid_refused(self):
        raw = bytearray(fixture())
        struct.pack_into('<I', raw, 16, 5)
        struct.pack_into('<I', raw, 20, 160)
        struct.pack_into('<II16s', raw, 168, 0x1b, 24, b'\0' * 16)
        with self.assertRaises(ValueError):
            inspect_bytes(bytes(raw), '_AVD_CreateAVDAccelerator')
