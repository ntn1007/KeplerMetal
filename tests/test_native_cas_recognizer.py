"""Offline safety checks; synthetic instructions are never sent to a GPU."""
import struct
import sys
import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge/tools'))
from recognize_native_cas import register_references, sass_contract
import recognize_native_cas as cas


def listing(extra='nop', address=8, after_store='exit'):
    ops = [
        'sched 0x0', 'ld lock $p1 $r4 s[0x4]',
        '$p1 set b32 $r2 eq s32 $r4 $r0',
        '$p1 slct b32 $r5 $r1 $r4 ne s32 $r2',
        '$p1 st unlock $p0 s[0x4] $r5', '(not $p0) bra 0x8',
        'set $p0 0x1 eq u32 $r0 $r4', 'membar cta',
        'sched 0x0', extra, f'st b128 wb g[$r{address}d] $r0q',
        after_store, 'nop', 'nop', 'nop', 'nop',
    ]
    words = [0] * len(ops)
    words[7] = 0xe000000000001c05
    code = b''.join(struct.pack('<Q', word) for word in words)
    text = '\n'.join(
        f'{i * 8:08x}: {word & 0xffffffff:08x} {word >> 32:08x}     {op}'
        for i, (word, op) in enumerate(zip(words, ops))
    )
    return code, text


class CASRecognitionSafety(unittest.TestCase):
    def test_ordinary_output_is_accepted(self):
        code, text = listing()
        self.assertTrue(sass_contract(code, text, 0)['qualified'])

    def test_extra_consumer_is_rejected(self):
        code, text = listing(extra='mov b32 $r5 $r0')
        self.assertFalse(sass_contract(code, text, 0)['qualified'])

    def test_duplicated_line_cannot_hide_extra_consumer(self):
        code, text = listing(extra='mov b32 $r5 $r0')
        rows = text.splitlines()
        rows[9] = rows[12]  # Duplicate a genuine word while omitting offset 72.
        result = sass_contract(code, '\n'.join(rows), 0)
        self.assertFalse(result['qualified'])
        self.assertIn('offsets', result['reason'])

    def test_out_of_order_or_missing_lines_are_rejected(self):
        code, text = listing()
        rows = text.splitlines()
        swapped = rows.copy()
        swapped[9], swapped[10] = swapped[10], swapped[9]
        for bad in (swapped, rows[:9] + rows[10:], rows[:-1]):
            with self.subTest(lines=bad):
                self.assertFalse(sass_contract(code, '\n'.join(bad), 0)['qualified'])

    def test_schedule_word_cannot_be_duplicated(self):
        code, text = listing()
        rows = text.splitlines()
        rows[8] = rows[0]
        self.assertFalse(sass_contract(code, '\n'.join(rows), 0)['qualified'])

    def test_consumer_after_store_is_rejected(self):
        code, text = listing(after_store='mov b32 $r5 $r0')
        self.assertFalse(sass_contract(code, text, 0)['qualified'])

    def test_address_alias_is_rejected(self):
        code, text = listing(address=0)
        self.assertFalse(sass_contract(code, text, 0)['qualified'])

    def test_vector_alias_is_expanded(self):
        self.assertEqual(register_references('mov b128 $r3q $r7d'), {3, 4, 5, 6, 7, 8})
        code, text = listing(extra='mov b128 $r8q $r0q')
        self.assertFalse(sass_contract(code, text, 0)['qualified'])

    def test_invalid_component_is_rejected(self):
        code, text = listing()
        for value in (-1, 4, True, '0'):
            with self.subTest(value=value):
                self.assertFalse(sass_contract(code, text, value)['qualified'])

    def test_decoder_reproduction_is_pinned_and_exact(self):
        with tempfile.TemporaryDirectory() as directory:
            decoder = Path(directory) / 'decoder'
            decoder.write_bytes(b'#!/bin/sh\n[ -z "$DYLD_KEPLER_TEST" ] || exit 9\nprintf "trusted listing\\n"\n')
            pin = hashlib.sha256(decoder.read_bytes()).hexdigest()
            with mock.patch.object(cas, 'ENVYDIS_SHA256', pin), mock.patch.dict(os.environ, {'DYLD_KEPLER_TEST': 'must-not-pass'}):
                self.assertTrue(cas.verify_decoder(b'code', 'trusted listing\n', decoder))
                self.assertFalse(cas.verify_decoder(b'code', 'tampered listing\n', decoder))
                self.assertFalse(cas.verify_decoder(b'code', 'trusted listing\n', None))
                decoder.write_bytes(decoder.read_bytes() + b'# changed\n')
                self.assertFalse(cas.verify_decoder(b'code', 'trusted listing\n', decoder))

    def test_qualification_refuses_without_decoder(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('test.metal', 'test.air', 'test.metallib', 'native.sass', 'native.asm'):
                (root / name).write_bytes(b'original')
            (root / 'typed-air.json').write_bytes(b'{}')
            with mock.patch.object(cas, 'air_contract', return_value={'qualified': True, 'expected_output_component': 0}):
                result = cas.recognize(root)
            self.assertFalse(result['qualified'])
            self.assertFalse(result['decoder_reproduced_listing'])

    def test_recognizer_hashes_the_snapshot_it_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ('test.metal', 'test.air', 'test.metallib', 'native.sass', 'native.asm'):
                (root / name).write_bytes(b'original')
            (root / 'typed-air.json').write_bytes(b'{}')
            def modify_after_snapshot(code, listing, decoder):
                (root / 'native.sass').write_bytes(b'changed')
                return True
            with mock.patch.object(cas, 'air_contract', return_value={'qualified': True, 'expected_output_component': 0}), \
                 mock.patch.object(cas, 'verify_decoder', side_effect=modify_after_snapshot), \
                 mock.patch.object(cas, 'sass_contract', return_value={'qualified': True}):
                result = cas.recognize(root, 'stub')
            self.assertEqual(result['hashes']['native.sass'], hashlib.sha256(b'original').hexdigest())
            self.assertNotEqual(result['hashes']['native.sass'], hashlib.sha256((root / 'native.sass').read_bytes()).hexdigest())


if __name__ == '__main__':
    unittest.main()
