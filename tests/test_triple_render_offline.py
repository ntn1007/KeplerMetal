# SPDX-License-Identifier: MIT
"""Structural checks for triple lowering; compilation is not GPU execution."""
import json
from pathlib import Path
import re
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'bridge/tools'))
from air_triple_render_lowering import lower,PIPELINE,VERTEX,INDEXED
from air_reset_lowering import entry_body
from verify_triple_render import choices


class TripleRenderLowering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.ir=json.loads((ROOT/'tests/fixtures/air_triple_render_ir.json').read_text())['IR']

    def test_entry_dataflow_is_unchanged_except_operation_names(self):
        expected=entry_body(self.ir).replace('@'+PIPELINE,'@kp_set_render_pipeline').replace('@'+VERTEX,'@kp_set_vertex_buffer')
        for bits,name in INDEXED.items():expected=expected.replace('@'+name,'@kp_indexed_render_'+str(bits))
        expected=expected.replace('@air.reset_render_command','@kp_reset_render_command')
        self.assertEqual(entry_body(lower(self.ir)),expected)

    def test_pipeline_walks_bounded_index_and_vertex_headers(self):
        text=lower(self.ir);body=text.split('define internal void @kp_set_render_pipeline(',1)[1].split('\n}',1)[0]
        for marker in ('%imagic = icmp eq i32','%vmagic = icmp eq i32','%pmagic = icmp eq i32',
                       '%pcounthigh = icmp ule i32 %pe2, 64','%ptableok = icmp eq i64',
                       '%bindingok = icmp eq i32 %b4, 0','ptrtoint %struct._render_pipeline_state_t addrspace(1)* %pipeline to i64'):
            self.assertIn(marker,body)
        self.assertLess(body.index('%imagic'),body.index('%vmagic'));self.assertLess(body.index('%vmagic'),body.index('%pmagic'))
        self.assertNotRegex(body,r'load [^\n]*\* %pipeline,')

    def test_unknown_commands_and_changed_root_are_rejected(self):
        with self.assertRaises(ValueError):lower(self.ir+'\ndeclare void @air.set_fragment_buffer_render_command()\n')
        with self.assertRaises(ValueError):lower(self.ir.replace('!"air.buffer_size", i32 16','!"air.buffer_size", i32 8'))
        with self.assertRaises(ValueError):lower(self.ir.replace('@'+INDEXED[16],'@air.unknown_indexed_render_command'))

    def test_metadata_renumbering_keeps_entry(self):
        changed=re.sub(r'!(\d+)',lambda m:'!'+str(int(m[1])+100),self.ir)
        self.assertEqual(entry_body(lower(changed)),re.sub(r'!(\d+)',lambda m:'!'+str(int(m[1])+100),entry_body(lower(self.ir))))

    def test_cpu_oracle_distinguishes_the_two_independent_setters(self):
        for suffix in ('','_native'):
            self.assertEqual(choices('no_dispatch'+suffix),(False,False))
            self.assertEqual(choices('vertex_only'+suffix),(True,False))
            self.assertEqual(choices('pipeline_only'+suffix),(False,True))
            self.assertEqual(choices('reverse'+suffix),(False,False))
        self.assertEqual(choices('gpu'),(True,True))
        self.assertEqual(choices('native'),(True,True))
        self.assertEqual(choices('contracts'),(True,True))
        with self.assertRaises(AssertionError):choices('unknown')
