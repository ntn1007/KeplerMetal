# SPDX-License-Identifier: MIT
import json
from dataclasses import replace
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'bridge/tools'))
from air_vertex_binding_lowering import lower, SET
from air_reset_lowering import entry_body
from air_vertex_transition import Binding, State, ROW, make_rows, pack_rows, select


class VertexBindingLowering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ir = json.loads((ROOT / 'tests/fixtures/air_vertex_binding_ir.json').read_text())['IR']

    def test_preserves_entry_dataflow_and_operation_order(self):
        expected = entry_body(self.ir).replace('@' + SET, '@kp_set_vertex_buffer')
        expected = expected.replace('@air.draw_primitives_render_command', '@kp_draw_primitives_render_command')
        self.assertEqual(entry_body(lower(self.ir)), expected)
        self.assertLess(expected.index('@kp_set_vertex_buffer'), expected.index('@kp_draw_primitives'))

    def test_does_not_dereference_untrusted_vertex_pointer(self):
        translated = lower(self.ir)
        self.assertIn('ptrtoint i8 addrspace(1)* %buffer to i64', translated)
        self.assertNotRegex(translated, r'load [^\n]*\* %buffer,')
        self.assertIn('store i64 %b1, i64 addrspace(1)* %idptr', translated)

    def test_constant_pointer_and_dynamic_stride_rejected(self):
        with self.assertRaises(ValueError):
            lower(self.ir.replace('p1i8', 'p2i8').replace('i8 addrspace(1)*', 'i8 addrspace(2)*'))
        call = next(x for x in self.ir.splitlines() if 'call void @' + SET in x)
        with self.assertRaises(ValueError):
            lower(self.ir.replace(call, call.replace('i64 -1', 'i64 16')))

    def test_incompatible_and_unknown_commands_rejected(self):
        with self.assertRaises(ValueError):
            lower(self.ir + '\ndeclare void @air.set_fragment_buffer_render_command()\n')
        declaration = next(x for x in self.ir.splitlines() if x.startswith('declare void @' + SET))
        with self.assertRaises(ValueError):
            lower(self.ir.replace(declaration, declaration.replace('i64, i32', 'i32, i32')))

    def test_metadata_renumbering(self):
        updated = re.sub(r'!(\d+)', lambda m: '!' + str(int(m[1]) + 100), self.ir)
        self.assertEqual(entry_body(lower(updated)), re.sub(r'!(\d+)', lambda m: '!' + str(int(m[1]) + 100), entry_body(lower(self.ir))))


class VertexTransitionModel(unittest.TestCase):
    def setUp(self):
        self.a = Binding(11, 0x10000, 64, 4096)
        self.b = Binding(12, 0x20000, 64, 4096)
        self.instance = Binding(13, 0x30000, 128, 4096)
        self.src = State(101, 1, 7, ((0, self.a), (1, self.instance)), ((0, 99),), (55, 64, 1), (6, 1, 2, 1))
        self.dst = replace(self.src, identity=102, vertices=((0, self.b), (1, self.instance)))

    def test_complete_transition_and_reverse_preserve_other_state(self):
        rows = make_rows([self.src, self.dst])
        self.assertEqual(select(rows, 101, self.b.pointer(), 1, 0), 102)
        self.assertEqual(select(rows, 102, self.a.pointer(), 1, 0), 101)
        self.assertEqual(select(rows, 101, self.a.pointer(), 1, 0), 101)
        self.assertEqual(len(pack_rows(rows)), len(rows) * ROW.size)
        self.assertTrue(all(ROW.unpack_from(pack_rows(rows), i * ROW.size) == row for i, row in enumerate(rows)))

    def test_two_ordered_setters_reach_the_matching_composite_state(self):
        other = Binding(14, 0x40000, 128, 4096)
        second = replace(self.src, identity=103, vertices=((0, self.a), (1, other)))
        both = replace(self.src, identity=104, vertices=((0, self.b), (1, other)))
        rows = make_rows([self.src, self.dst, second, both])
        first = select(rows, 101, self.b.pointer(), 1, 0)
        self.assertEqual(first, 102)
        self.assertEqual(select(rows, first, other.pointer(), 1, 1), 104)
        second_first = select(rows, 101, other.pointer(), 1, 1)
        self.assertEqual(second_first, 103)
        self.assertEqual(select(rows, second_first, self.b.pointer(), 1, 0), 104)

    def test_wrong_slot_binding_pointer_stride_fail_closed(self):
        rows = make_rows([self.src, self.dst])
        for source, ptr, slot, bind, stride in [(101, self.b.pointer(), 0, 0, -1),
                (101, self.b.pointer(), 1, 1, -1), (101, self.b.pointer()+16, 1, 0, -1),
                (999, self.b.pointer(), 1, 0, -1), (101, self.b.pointer(), 1, 0, 16),
                (101, 0, 1, 0, -1)]:
            self.assertIsNone(select(rows, source, ptr, slot, bind, stride % (1 << 64)))

    def test_cannot_change_pipeline_fragment_index_other_binding_or_geometry(self):
        variants = [replace(self.dst, pipeline=8), replace(self.dst, fragments=((0, 100),)),
                    replace(self.dst, index_binding=(56, 64, 1)), replace(self.dst, geometry=(3, 1, 2, 1)),
                    replace(self.dst, vertices=((0, self.b), (1, Binding(14, 0x40000, 128, 4096))))]
        for dst in variants:
            with self.subTest(dst=dst):
                self.assertIsNone(select(make_rows([self.src, dst]), 101, self.b.pointer(), 1, 0))

    def test_aliasing_different_destinations_rejected(self):
        alias = Binding(22, self.b.address, self.b.offset, self.b.length)
        ambiguous = replace(self.dst, identity=103, vertices=((0, alias), (1, self.instance)))
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            make_rows([self.src, self.dst, ambiguous])

    def test_duplicate_id_bad_alignment_and_out_of_profile_rejected(self):
        with self.assertRaises(ValueError): make_rows([self.src, self.src])
        for b in (Binding(1, 0x10000, 1, 4096), Binding(1, (1 << 40)-16, 16, 16),
                  Binding(1, 0, 0, 10), Binding(1, 0x10000, 32, 16)):
            with self.subTest(binding=b), self.assertRaises(ValueError):
                make_rows([replace(self.src, vertices=((0, b),))])

    def test_bound_rejected_rather_than_truncated(self):
        with self.assertRaisesRegex(ValueError, 'State count'):
            make_rows([replace(self.src, identity=i + 1) for i in range(17)])
        states = [replace(self.src, identity=i+1, vertices=((0, Binding(i+1, 0x10000*(i+1), 64, 4096)),)) for i in range(9)]
        with self.assertRaisesRegex(ValueError, 'row count'):
            make_rows(states)
