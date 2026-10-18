# SPDX-License-Identifier: MIT
"""Synthetic Mach-O import names; no cache, vendor code or native execution."""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge/tools'))
from inspect_video_cache import stub_symbol


class MemoryCache:
    def __init__(self, data):
        self.data = bytes(data)

    def read(self, address, size):
        offset = address - 0x800000
        if not 0 <= offset <= offset + size <= len(self.data):
            raise ValueError('synthetic cache bounds')
        return self.data[offset:offset + size]


def fixture(kind=1, index=0, name=b'_public_import\0'):
    data = bytearray(256)
    struct.pack_into('<I', data, 0, index)
    struct.pack_into('<IBBHQ', data, 64, 1, kind, 1 if kind == 15 else 0,
                     0, 0x900000 if kind == 15 else 0)
    data[129:129 + len(name)] = name
    image = {
        'sections': [{'flags': 8, 'VM_address': 0x400000, 'size': 12,
                      'reserved1': 0, 'reserved2': 6}],
        'segments': [{'name': '__LINKEDIT', 'VM_address': 0x800000,
                      'file_offset': 0x1000, 'file_size': len(data)}],
        'indirect_symbol_table': {'file_offset': 0x1000, 'count': 1},
        'symbol_table': {'file_offset': 0x1040, 'count': 1,
                         'strings_offset': 0x1080, 'strings_size': len(name) + 1}}
    return MemoryCache(data), image


class CacheImportIdentity(unittest.TestCase):
    def test_undefined_external_has_only_static_identity(self):
        cache, image = fixture()
        row = stub_symbol(cache, image, 0x400000)
        self.assertEqual(row['static_symbol'], '_public_import')
        self.assertFalse(row['runtime_target_proved'])

    def test_defined_index_zero_is_not_an_import(self):
        cache, image = fixture(kind=15, name=b'_different_defined_body\0')
        row = stub_symbol(cache, image, 0x400000)
        self.assertIsNone(row['static_symbol'])
        self.assertEqual(row['symbol_table_candidate'], '_different_defined_body')
        self.assertEqual(row['nlist_value'], 0x900000)
        self.assertFalse(row['binding_name_proved'])
        self.assertFalse(row['runtime_target_proved'])

    def test_debug_and_non_external_symbols_are_not_callees(self):
        for kind in [0, 0xe1]:
            with self.subTest(kind=kind):
                cache, image = fixture(kind=kind)
                self.assertIsNone(stub_symbol(cache, image, 0x400000)['static_symbol'])

    def test_misaligned_stub_is_refused(self):
        cache, image = fixture()
        with self.assertRaisesRegex(ValueError, 'stub alignment'):
            stub_symbol(cache, image, 0x400001)

    def test_indirect_local_marker_is_not_a_symbol_index(self):
        for index in [1, 0x80000000]:
            with self.subTest(index=index):
                cache, image = fixture(index=index)
                with self.assertRaisesRegex(ValueError, 'named symbol index'):
                    stub_symbol(cache, image, 0x400000)

    def test_unterminated_name_is_refused(self):
        cache, image = fixture(name=b'_unterminated')
        with self.assertRaisesRegex(ValueError, 'unterminated string'):
            stub_symbol(cache, image, 0x400000)


if __name__ == '__main__':
    unittest.main()
