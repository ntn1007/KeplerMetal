#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Experimental bounded typed render-pipeline lowering, not GPU qualification.

The resulting two-word root and context table are project-owned. A caller must
provide retained, certified resources. This is not an Apple ICB ABI or a GPU
pointer sandbox. Do not dispatch arbitrary inputs or fabricated contexts.
"""
import re
from lower_air_render_reset import normalized, helper as reset_helper
from air_reset_lowering import entry_body
from air_render_draw_lowering import draw_helper, DRAW
from air_vertex_binding_lowering import setter_helper, EXT_MAGIC

SET = 'air.set_pipeline_state_render_command'
RESET = 'air.reset_render_command'
PIPELINE_MAGIC = 0x4b505050


def pipeline_helper():
    text = setter_helper()
    changes = {
        '@kp_set_vertex_buffer(': '@kp_set_render_pipeline(',
        'i8 addrspace(1)* %buffer, i64 %stride, i32 %binding':
            '%struct._render_pipeline_state_t addrspace(1)* %pipeline',
        'ptrtoint i8 addrspace(1)* %buffer to i64':
            'ptrtoint %struct._render_pipeline_state_t addrspace(1)* %pipeline to i64',
        '  %strideok = icmp eq i64 %stride, -1\n': '',
        '%ext3 = and i1 %etable, %strideok': '%ext3 = and i1 %etable, true',
        '%bindingok = icmp eq i32 %b4, %binding': '%bindingok = icmp eq i32 %b4, 0',
        str(EXT_MAGIC): str(PIPELINE_MAGIC),
    }
    for old, new in changes.items():
        if text.count(old) != 1:
            raise ValueError('Unexpected underlying helper shape')
        text = text.replace(old, new)
    return text


def rewrite_pipeline_root(text):
    pairs = re.findall(r'^!(\d+) = (.*)$', text, re.M)
    nodes = dict(pairs)
    if len(nodes) != len(pairs):
        raise ValueError('Duplicate metadata node')
    roots = [(k, v) for k, v in nodes.items() if '!"air.indirect_buffer"' in v]
    if len(roots) != 1:
        raise ValueError('One indirect root required')
    root, value = roots[0]
    pattern = (r'!\{i32 0, !"air.indirect_buffer", !"air.buffer_size", i32 16, '
               r'!"air.location_index", i32 0, i32 1, !"air.read_write", !"air.address_space", i32 1, '
               r'!"air.struct_type_info", !(\d+), !"air.arg_type_size", i32 16, '
               r'!"air.arg_type_align_size", i32 8, !"air.arg_type_name", !"Arguments", !"air.arg_name", !"args"\}')
    match = re.fullmatch(pattern, value)
    if not match:
        raise ValueError('Root layout differs')
    child = match[1]
    match = re.fullmatch(r'!\{i32 0, i32 8, i32 0, !"command_buffer", !"commands", !"air.indirect_argument", !(\d+), '
                         r'i32 8, i32 8, i32 0, !"render_pipeline_state", !"pipeline", !"air.indirect_argument", !(\d+)\}', nodes.get(child, ''))
    if not match:
        raise ValueError('Root members differ')
    command, pipeline = match.groups()
    if nodes.get(command) != '!{i32 0, !"air.command_buffer", !"air.location_index", i32 0, i32 1, !"air.arg_type_name", !"command_buffer", !"air.arg_name", !"commands"}':
        raise ValueError('Command member differs')
    if nodes.get(pipeline) != '!{i32 1, !"air.render_pipeline_state", !"air.location_index", i32 1, i32 1, !"air.arg_type_name", !"render_pipeline_state", !"air.arg_name", !"pipeline"}':
        raise ValueError('Pipeline member differs')
    for node in (child, command, pipeline):
        if len(re.findall(r'!' + node + r'(?!\d)', text)) != 2:
            raise ValueError('Shared root metadata refused')
    if '%struct.Arguments = type { %"struct.metal::command_buffer", %"struct.metal::render_pipeline_state" }' not in text:
        raise ValueError('LLVM root layout differs')
    value = value.replace('!"air.indirect_buffer"', '!"air.buffer"').replace('!"air.read_write"', '!"air.read"')
    text = re.sub(r'^!' + root + r' = .*$', '!' + root + ' = ' + value, text, flags=re.M)
    members = '!{i32 0, i32 8, i32 0, !"ulong", !"context", i32 8, i32 8, i32 0, !"ulong", !"pipeline"}'
    text = re.sub(r'^!' + child + r' = .*$', '!' + child + ' = ' + members, text, flags=re.M)
    for node in (command, pipeline):
        text = re.sub(r'^!' + node + r' = .*\n', '', text, flags=re.M)
    if any(x in text for x in ('!"air.indirect_buffer"', '!"air.command_buffer"', '!"air.render_pipeline_state"')):
        raise ValueError('Residual resource metadata')
    return text


def lower(ir):
    text = normalized(ir)
    before = entry_body(text)
    if '@kp_' in text:
        raise ValueError('Helper collision')
    names = re.findall(r'@air\.[\w.]*command[\w.]*', text)
    allowed = {'@' + SET, '@' + DRAW, '@' + RESET}
    if set(names) - allowed or '@' + SET not in names or '@' + DRAW not in names:
        raise ValueError('Expected pipeline setter and triangle draw only')
    mapping = {
        SET: ('kp_set_render_pipeline', pipeline_helper(),
              '%struct._command_buffer_t addrspace(1)* nocapture, i32, %struct._render_pipeline_state_t addrspace(1)* readonly', 3),
        DRAW: ('kp_draw_primitives_render_command', draw_helper(),
               '%struct._command_buffer_t addrspace(1)* nocapture, i32, i32, i32, i32, i32, i32', 7),
        RESET: ('kp_reset_render_command', reset_helper(),
                '%struct._command_buffer_t addrspace(1)* nocapture, i32', 2),
    }
    expected = before
    for name, (replacement, helper, signature, arity) in mapping.items():
        if '@' + name not in names:
            continue
        decl = re.findall(r'^declare void @' + re.escape(name) + r'\(' + re.escape(signature) +
                          r'\) local_unnamed_addr #\d+$', text, re.M)
        calls = re.findall(r'\bcall void @' + re.escape(name) + r'\(([^\n]+)\)', before)
        if len(decl) != 1 or not calls or len(calls) + 1 != names.count('@' + name):
            raise ValueError('Operation declaration or call differs')
        for call in calls:
            args = call.split(', ')
            if len(args) != arity or not re.fullmatch(r'%struct\._command_buffer_t addrspace\(1\)\* nocapture %\w+', args[0]):
                raise ValueError('Command operand differs')
            if name == SET:
                if not re.fullmatch(r'%struct\._render_pipeline_state_t addrspace\(1\)\* readonly %\w+', args[2]):
                    raise ValueError('Pipeline operand differs')
                scalars = args[1:2]
            else:
                if name == DRAW and args[2] != 'i32 3':
                    raise ValueError('Only triangle primitives supported')
                scalars = args[1:]
            if any(not re.fullmatch(r'i32 (?:%\w+|-?\d+)', x) for x in scalars):
                raise ValueError('Scalar operand differs')
        text = text.replace(decl[0], helper).replace('@' + name + '(', '@' + replacement + '(')
        expected = expected.replace('@' + name + '(', '@' + replacement + '(')
    text = rewrite_pipeline_root(text)
    if entry_body(text) != expected or re.search(r'@air\.[\w.]*command[\w.]*', text):
        raise ValueError('Residual or changed command dataflow')
    return "; ModuleID = 'keplermetal-pipeline-binding-experiment'\n" + text
