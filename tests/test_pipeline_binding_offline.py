# SPDX-License-Identifier: MIT
"""Strict offline translation checks; no GPU execution is implied."""
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'bridge/tools'))
from air_pipeline_binding_lowering import lower, SET
from air_reset_lowering import entry_body


class PipelineBindingLowering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ir = json.loads((ROOT/'tests/fixtures/air_pipeline_binding_ir.json').read_text())['IR']

    def test_preserves_entry_dataflow_and_order(self):
        expected = entry_body(self.ir).replace('@'+SET, '@kp_set_render_pipeline')
        expected = expected.replace('@air.draw_primitives_render_command', '@kp_draw_primitives_render_command')
        output = lower(self.ir)
        self.assertEqual(entry_body(output), expected)
        self.assertLess(expected.index('@kp_set_render_pipeline'), expected.index('@kp_draw_primitives'))
        self.assertNotIn('!"air.indirect_buffer"', output)
        self.assertNotIn('!"air.render_pipeline_state"', output)
        self.assertIn('!"ulong", !"context", i32 8, i32 8, i32 0, !"ulong", !"pipeline"', output)

    def test_token_is_compared_not_dereferenced(self):
        output = lower(self.ir)
        self.assertIn('ptrtoint %struct._render_pipeline_state_t addrspace(1)* %pipeline to i64', output)
        self.assertNotRegex(output, r'load [^\n]*\* %pipeline,')
        self.assertIn('%bindingok = icmp eq i32 %b4, 0', output)
        self.assertIn('store i64 %b1, i64 addrspace(1)* %idptr', output)

    def test_unknown_operations_and_operand_shapes_refused(self):
        with self.assertRaises(ValueError):
            lower(self.ir + '\ndeclare void @air.set_fragment_buffer_render_command()\n')
        call = next(line for line in self.ir.splitlines() if 'call void @'+SET in line)
        with self.assertRaises(ValueError):
            lower(self.ir.replace(call, call.replace('readonly %9', 'readonly null')))
        with self.assertRaises(ValueError):
            lower(self.ir.replace('i32 3, i32 0, i32 3, i32 1, i32 0)', 'i32 4, i32 0, i32 3, i32 1, i32 0)'))

    def test_metadata_shape_and_shared_nodes_refused(self):
        with self.assertRaises(ValueError):
            lower(self.ir.replace('!"air.buffer_size", i32 16', '!"air.buffer_size", i32 8'))
        with self.assertRaises(ValueError):
            lower(self.ir.replace('!"pipeline", !"air.indirect_argument", !21', '!"pipeline", !"air.indirect_argument", !20'))
        with self.assertRaisesRegex(ValueError, 'Shared'):
            lower(self.ir + '\n!999 = !{!20}\n')

    def test_metadata_renumbering(self):
        renumbered = re.sub(r'!(\d+)', lambda m: '!'+str(int(m[1])+100), self.ir)
        self.assertEqual(entry_body(lower(renumbered)),
                         re.sub(r'!(\d+)', lambda m: '!'+str(int(m[1])+100), entry_body(lower(self.ir))))
