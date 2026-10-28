"""Offline container and branch-shape counterexamples; no GPU execution."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'bridge/experiments/cas_divergence'))
from analyze_indirect import examine, sections


def instructions():
    return [(0x268, 'add b32 $r0 $r0 0xfffffffe'),
            (0x270, 'min u32 $r0 $r0 0x2'),
            (0x278, 'shl b32 $r0 $r0 clamp 0x2'),
            (0x288, 'ld b32 $r1 c0[$r0]'),
            (0x290, 'bra $r1 0x0'),
            (0x298, 'nop'), (0x2b8, 'nop'), (0x330, 'nop')]


def container():
    first = struct.pack('<QII', 24, 1, 4) + b'ABCD' + b'\0'*4
    last = struct.pack('<QII', 0, 0x10006, 12) + struct.pack('<III', 0x298, 0x2b8, 0x330) + b'\0'*4
    return struct.pack('<II', 9, 8+len(first)+len(last)) + first + last


class IndirectBranch(unittest.TestCase):
    def test_conditional_observation_does_not_authorize_repair(self):
        result = examine(instructions(), sections(container())[0x10006])
        self.assertEqual(result['conditional_index_offsets'], [0, 4, 8])
        self.assertFalse(result['constant_bank_binding_proved'])
        self.assertFalse(result['authorizes_repair'])

    def test_short_table_and_changed_targets_rejected(self):
        data = struct.pack('<III', 0x298, 0x2b8, 0x330)
        for bad in (data[:-1], struct.pack('<III', 0x298, 0x2b8, 0x338)):
            with self.assertRaises(ValueError): examine(instructions(), bad)

    def test_changed_index_load_and_indirect_branch_rejected(self):
        data = sections(container())[0x10006]
        for index, replacement in ((1, 'min u32 $r0 $r0 0x3'),
                                   (3, 'ld b32 $r1 c1[$r0]'),
                                   (4, 'bra $r2 0x0')):
            ins = instructions(); ins[index] = (ins[index][0], replacement)
            with self.subTest(index=index), self.assertRaises(ValueError): examine(ins, data)

    def test_incoming_direct_edge_and_extra_indirect_rejected(self):
        data = sections(container())[0x10006]
        for extra in ((0x100, '$p0 bra 0x278'), (0x100, 'bra $r3 0x0')):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                examine(instructions()+[extra], data)

    def test_truncated_duplicate_and_nonzero_padding_rejected(self):
        raw=bytearray(container())
        bad_length=raw.copy(); struct.pack_into('<I',bad_length,4,len(bad_length)-1)
        duplicate=raw.copy(); struct.pack_into('<I',duplicate,8+24+8,1)
        bad_padding=raw.copy(); bad_padding[-1]=1
        for bad in (bad_length,duplicate,bad_padding,raw[:-1]):
            with self.assertRaises(ValueError): sections(bytes(bad))


if __name__ == '__main__': unittest.main()
