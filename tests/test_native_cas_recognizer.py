"""Offline safety checks; synthetic instructions are never sent to a GPU."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge/tools'))
from recognize_native_cas import register_references, sass_contract


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


if __name__ == '__main__':
    unittest.main()
