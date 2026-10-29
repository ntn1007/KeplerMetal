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
    @staticmethod
    def air_fixture():
        # Synthetic typed-AIR model, not an encoded or GPU-executable shader.
        types = [dict(kind=2, bits=32), dict(kind=3, address_space=3, element=0),
                 dict(kind=3, address_space=0, element=0),
                 dict(kind=4, count=4, element=0),
                 dict(kind=3, address_space=1, element=0)]
        values = [dict(type=1), dict(type=2), dict(type=0), dict(type=3),
                  dict(type=0, kind=2, integer=0), dict(type=3), dict(type=4), dict(type=0)]
        instructions = [
            dict(index=0, block=0, op=16, callee='air.atomic.local.cmpxchg.weak.i32',
                 type=0, operands=[99, 0, 1], value=7),
            dict(index=1, block=0, op=14, type=0, operands=[1], value=2),
            dict(index=2, block=0, op=5, type=3, operands=[3, 2, 4], value=5),
            dict(index=3, block=0, op=15, type=0, operands=[6, 5], value=999),
        ]
        return dict(types=types, functions=[dict(name='test', values=values, instructions=instructions)])

    def test_air_output_chain_must_stay_in_the_post_cas_block(self):
        module = self.air_fixture()
        self.assertTrue(cas.air_contract(module)['qualified'])
        for position in (2, 3):
            with self.subTest(position=position):
                altered = self.air_fixture()
                altered['functions'][0]['instructions'][position]['block'] = 1
                self.assertFalse(cas.air_contract(altered)['qualified'])

    def test_air_output_path_cannot_cross_a_control_terminator(self):
        for op in (8, 9, 10, 12):
            module = self.air_fixture()
            instructions = module['functions'][0]['instructions']
            instructions.insert(2, dict(index=2, block=0, op=op, operands=[], value=998))
            instructions[3]['index'] = 3
            instructions[4]['index'] = 4
            with self.subTest(op=op):
                self.assertFalse(cas.air_contract(module)['qualified'])

    def test_join_modifier_keeps_underlying_register_writes(self):
        self.assertEqual(cas.register_writes('join nop'), set())
        self.assertEqual(cas.register_writes('join mov b32 $r9 $r6'), {9})
        self.assertEqual(cas.register_writes('join mov b64 $r9d $r6d'), {9, 10})
        self.assertEqual(cas.register_writes('$p1 join mov b32 $r0 $r6'), {0})
        self.assertIsNone(cas.register_writes('join unrecognized $r9 $r6'))
        self.assertIsNone(cas.register_writes('join'))

    def test_join_write_between_lock_and_comparison_is_rejected(self):
        code, text = listing()
        rows = text.splitlines()
        # Insert the combined operation into the lock-result live interval;
        # this is parser-only synthetic text, never GPU-executed.
        ops = [row.split('     ', 1)[1] for row in rows]
        ops[6:11] = ['join mov b32 $r4 $r6', 'set $p0 0x1 eq u32 $r0 $r4',
                     'sched 0x0', 'membar cta', 'st b128 wb g[$r8d] $r0q']
        words = [0] * len(ops)
        words[9] = 0xe000000000001c05
        code = b''.join(struct.pack('<Q', word) for word in words)
        text = '\n'.join(f'{i * 8:08x}: {word & 0xffffffff:08x} {word >> 32:08x}     {op}'
                         for i, (word, op) in enumerate(zip(words, ops)))
        self.assertFalse(sass_contract(code, text, 0)['qualified'])
        self.assertTrue(sass_contract(code, text.replace('join mov b32 $r4 $r6', 'join nop'), 0)['qualified'])

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

    def test_register_indexed_shared_address(self):
        code, text = listing()
        indexed = text.replace('s[0x4]', 's[$r6]')
        result = sass_contract(code, indexed, 0)
        self.assertTrue(result['qualified'])
        self.assertEqual(result['shared_address'], '$r6')
        for register in (0, 2, 4, 5, 24):
            with self.subTest(register=register):
                self.assertFalse(sass_contract(code, text.replace('s[0x4]', f's[$r{register}]'), 0)['qualified'])
        self.assertFalse(sass_contract(code, indexed.replace('st unlock $p0 s[$r6]', 'st unlock $p0 s[$r7]'), 0)['qualified'])

    def test_post_patch_control_flow_cannot_reenter_cas(self):
        for position in ('extra', 'after_store'):
            for operation in ('bra 0x8', '$p1 bra 0x10', 'joinat 0x20'):
                with self.subTest(position=position, operation=operation):
                    code, text = listing(**{position: operation})
                    self.assertFalse(sass_contract(code, text, 0)['qualified'])

    def test_forward_branch_does_not_trip_backedge_rule(self):
        code, text = listing(extra='bra 0x58')
        self.assertTrue(sass_contract(code, text, 0)['qualified'])

    def test_branch_after_lock_cannot_bypass_the_correction(self):
        # These are synthetic decoder-shaped listings only; no SASS encoding or
        # execution claim follows from the matching word placeholders.
        for branch in ('bra 0x58', '$p1 bra 0x58', '(not $p1) bra 0x58', 'bra 0x40'):
            ops = ['sched 0x0', 'ld lock $p1 $r4 s[0x4]',
                   '$p1 set b32 $r2 eq s32 $r4 $r0',
                   '$p1 slct b32 $r5 $r1 $r4 ne s32 $r2',
                   '$p1 st unlock $p0 s[0x4]', '(not $p0) bra 0x8',
                   branch, 'set $p0 0x1 eq u32 $r0 $r4', 'sched 0x0',
                   'membar cta', 'nop', 'st b128 wb g[$r8d] $r0q',
                   'exit', 'nop', 'nop', 'nop']
            ops[4] += ' $r5'
            words = [0] * len(ops); words[9] = 0xe000000000001c05
            code = b''.join(struct.pack('<Q', word) for word in words)
            text = '\n'.join(f'{i*8:08x}: {word&0xffffffff:08x} {word>>32:08x}     {op}'
                             for i, (word, op) in enumerate(zip(words, ops)))
            with self.subTest(branch=branch):
                self.assertFalse(sass_contract(code, text, 0)['qualified'])

    def test_external_branch_cannot_skip_lock_or_enter_retry_sequence(self):
        for operation in ('bra 0x38', '$p1 bra 0x38', 'bra 0x18', '(not $p1) bra 0x18', 'bra 0x40'):
            ops=['sched 0x0',operation,'ld lock $p1 $r4 s[0x4]',
                 '$p1 set b32 $r2 eq s32 $r4 $r0',
                 '$p1 slct b32 $r5 $r1 $r4 ne s32 $r2',
                 '$p1 st unlock $p0 s[0x4] $r5','(not $p0) bra 0x10',
                 'set $p0 0x1 eq u32 $r0 $r4','sched 0x0','membar cta',
                 'st b128 wb g[$r8d] $r0q','exit','nop','nop','nop','nop']
            words=[0]*len(ops);words[9]=0xe000000000001c05
            code=b''.join(struct.pack('<Q',w) for w in words)
            text='\n'.join(f'{i*8:08x}: {w&0xffffffff:08x} {w>>32:08x}     {op}' for i,(w,op) in enumerate(zip(words,ops)))
            with self.subTest(operation=operation):
                self.assertFalse(sass_contract(code,text,0)['qualified'])

    def test_unmodeled_indirect_branch_before_lock_is_rejected(self):
        # Parser-level controls only: the words here are placeholders, not an
        # assembled shader, and the program is never dispatched.
        for operation in ('bra $r1 0x0', '$p1 bra $r1 0x0', '(not $p1) bra $r1 0x0',
                          'join bra $r1 0x0', 'joinat $r1 0x0'):
            ops=['sched 0x0',operation,'ld lock $p1 $r4 s[0x4]',
                 '$p1 set b32 $r2 eq s32 $r4 $r0',
                 '$p1 slct b32 $r5 $r1 $r4 ne s32 $r2',
                 '$p1 st unlock $p0 s[0x4] $r5','(not $p0) bra 0x10',
                 'set $p0 0x1 eq u32 $r0 $r4','sched 0x0','membar cta',
                 'st b128 wb g[$r8d] $r0q','exit','nop','nop','nop','nop']
            words=[0]*len(ops);words[9]=0xe000000000001c05
            code=b''.join(struct.pack('<Q',w) for w in words)
            text='\n'.join(f'{i*8:08x}: {w&0xffffffff:08x} {w>>32:08x}     {op}' for i,(w,op) in enumerate(zip(words,ops)))
            with self.subTest(operation=operation):
                result=sass_contract(code,text,0)
                self.assertFalse(result['qualified'])
                self.assertIn('unsupported branch',result['reason'])

    def test_reconvergence_target_cannot_enter_unmodeled_cas_region(self):
        for operation in ('joinat 0x18', 'joinat 0x38', 'joinat 0x40', '$p1 joinat 0x38'):
            ops=['sched 0x0',operation,'ld lock $p1 $r4 s[0x4]',
                 '$p1 set b32 $r2 eq s32 $r4 $r0',
                 '$p1 slct b32 $r5 $r1 $r4 ne s32 $r2',
                 '$p1 st unlock $p0 s[0x4] $r5','(not $p0) bra 0x10',
                 'set $p0 0x1 eq u32 $r0 $r4','sched 0x0','membar cta',
                 'st b128 wb g[$r8d] $r0q','exit','nop','nop','nop','nop']
            words=[0]*len(ops);words[9]=0xe000000000001c05
            code=b''.join(struct.pack('<Q',w) for w in words)
            text='\n'.join(f'{i*8:08x}: {w&0xffffffff:08x} {w>>32:08x}     {op}' for i,(w,op) in enumerate(zip(words,ops)))
            with self.subTest(operation=operation):
                self.assertFalse(sass_contract(code,text,0)['qualified'])

    def test_address_alias_is_rejected(self):
        code, text = listing(address=0)
        self.assertFalse(sass_contract(code, text, 0)['qualified'])

    def test_vector_alias_is_expanded(self):
        self.assertEqual(register_references('mov b128 $r3q $r7d'), {3, 4, 5, 6, 7, 8})
        code, text = listing(extra='mov b128 $r8q $r0q')
        self.assertFalse(sass_contract(code, text, 0)['qualified'])

    def test_register_floor_includes_all_vector_lanes(self):
        for op in ('mov b64 $r20d $r23d', 'mov b128 $r20q $r22q'):
            with self.subTest(op=op):
                code, text = listing(extra=op)
                result = sass_contract(code, text, 0)
                self.assertFalse(result['qualified'])
                self.assertIn('floor24', result['reason'])
        code, text = listing(extra='mov b128 $r20q $r20q')
        result = sass_contract(code, text, 0)
        self.assertTrue(result['qualified'])
        self.assertEqual(result['max_explicit_register'], 23)

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
