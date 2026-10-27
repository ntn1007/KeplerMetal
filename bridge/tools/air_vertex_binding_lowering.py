#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Experimental offline lowering for a bounded vertex-buffer setter.

Compilation is not GPU qualification. There is no production host, retained
resource ownership, or public API for this extension yet. Never dispatch the
result against an unowned or fabricated context. Unsupported operations refuse.
"""
import re
from lower_air_render_reset import normalized, helper as reset_helper
from air_reset_lowering import entry_body, rewrite_root
from air_render_draw_lowering import draw_helper, DRAW

SET = 'air.set_vertex_buffer_render_command.p1i8'
RESET = 'air.reset_render_command'
EXT_MAGIC = 0x4b505658
ROW_BYTES = 32
MAX_ROWS = 64


def setter_helper():
    text = reset_helper().split('  %q0 =')[0]
    text = text.replace('@kp_reset_render_command(', '@kp_set_vertex_buffer(')
    text = text.replace('i32 %index) alwaysinline',
        'i32 %index, i8 addrspace(1)* %buffer, i64 %stride, i32 %binding) alwaysinline')
    text += '''  %words = bitcast <4 x i32> addrspace(1)* %record to i32 addrspace(1)*
  %idword = getelementptr i32, i32 addrspace(1)* %words, i64 8
  %idptr = bitcast i32 addrspace(1)* %idword to i64 addrspace(1)*
  %identity = load i64, i64 addrspace(1)* %idptr, align 8
  %ctxbytes = bitcast %struct._command_buffer_t addrspace(1)* %opaque to i8 addrspace(1)*
  %extbytes = getelementptr i8, i8 addrspace(1)* %ctxbytes, i64 32
  %ext = bitcast i8 addrspace(1)* %extbytes to {i32, i32, i32, i32, i64, i64} addrspace(1)*
'''
    for i, t in enumerate(['i32'] * 4 + ['i64'] * 2):
        text += (f'  %ep{i} = getelementptr {{i32, i32, i32, i32, i64, i64}}, '
                 f'{{i32, i32, i32, i32, i64, i64}} addrspace(1)* %ext, i32 0, i32 {i}\n'
                 f'  %e{i} = load {t}, {t} addrspace(1)* %ep{i}, align {4 if i < 4 else 8}\n')
    text += f'''  %emagic = icmp eq i32 %e0, {EXT_MAGIC}
  %eversion = icmp eq i32 %e1, 1
  %countlow = icmp ugt i32 %e2, 0
  %counthigh = icmp ule i32 %e2, {MAX_ROWS}
  %entrybytes = icmp eq i32 %e3, {ROW_BYTES}
  %ereserved = icmp eq i64 %e5, 0
  %ctxaddress = ptrtoint %struct._command_buffer_t addrspace(1)* %opaque to i64
  %expectedtable = add i64 %ctxaddress, 64
  %etable = icmp eq i64 %e4, %expectedtable
  %strideok = icmp eq i64 %stride, -1
  %provided = ptrtoint i8 addrspace(1)* %buffer to i64
  %bufferlow = icmp ugt i64 %provided, 0
  %bufferhigh = icmp ult i64 %provided, 1099511627776
  %ext0 = and i1 %emagic, %eversion
  %ext1 = and i1 %countlow, %counthigh
  %ext2 = and i1 %entrybytes, %ereserved
  %ext3 = and i1 %etable, %strideok
  %ext4 = and i1 %bufferlow, %bufferhigh
  %ext5 = and i1 %ext0, %ext1
  %ext6 = and i1 %ext2, %ext3
  %ext7 = and i1 %ext5, %ext6
  %extok = and i1 %ext7, %ext4
  br i1 %extok, label %loop, label %refused
loop:
  %position = phi i32 [0, %reset], [%next, %advance]
  %position64 = zext i32 %position to i64
  %rowoffset = mul i64 %position64, {ROW_BYTES}
  %rowaddress = add i64 %e4, %rowoffset
  %row = inttoptr i64 %rowaddress to {{i64, i64, i64, i32, i32}} addrspace(1)*
'''
    for i, t in enumerate(['i64', 'i64', 'i64', 'i32', 'i32']):
        text += (f'  %bp{i} = getelementptr {{i64, i64, i64, i32, i32}}, '
                 f'{{i64, i64, i64, i32, i32}} addrspace(1)* %row, i32 0, i32 {i}\n'
                 f'  %b{i} = load {t}, {t} addrspace(1)* %bp{i}, align {8 if t == "i64" else 4}\n')
    text += '''  %srcok = icmp eq i64 %b0, %identity
  %nonzerosrc = icmp ne i64 %b0, 0
  %nonzerodst = icmp ne i64 %b1, 0
  %ptrok = icmp eq i64 %b2, %provided
  %slotok = icmp eq i32 %b3, %index
  %bindingok = icmp eq i32 %b4, %binding
  %match0 = and i1 %srcok, %nonzerosrc
  %match1 = and i1 %nonzerodst, %ptrok
  %match2 = and i1 %slotok, %bindingok
  %match3 = and i1 %match0, %match1
  %matched = and i1 %match3, %match2
  br i1 %matched, label %write, label %advance
advance:
  %next = add nuw i32 %position, 1
  %more = icmp ult i32 %next, %e2
  br i1 %more, label %loop, label %refused
write:
  store i64 %b1, i64 addrspace(1)* %idptr, align 8
  br label %exit
refused:
'''
    for i in range(4):
        text += (f'  %r{i} = getelementptr <4 x i32>, <4 x i32> addrspace(1)* %record, i64 {i}\n'
                 f'  store <4 x i32> zeroinitializer, <4 x i32> addrspace(1)* %r{i}, align 16\n')
    return text + '  br label %exit\nexit:\n  ret void\n}'


def lower(ir):
    text = normalized(ir)
    before = entry_body(text)
    if '@kp_' in text:
        raise ValueError('Helper name collision')
    names = re.findall(r'@air\.[\w.]*command[\w.]*', text)
    allowed = {'@' + SET, '@' + DRAW, '@' + RESET}
    if not names or set(names) - allowed or '@' + SET not in names or '@' + DRAW not in names:
        raise ValueError('Expected only vertex setter and typed draw/reset')
    mappings = {
        SET: ('kp_set_vertex_buffer', setter_helper(),
              '%struct._command_buffer_t addrspace(1)* nocapture, i32, i8 addrspace(1)*, i64, i32', 5),
        DRAW: ('kp_draw_primitives_render_command', draw_helper(),
               '%struct._command_buffer_t addrspace(1)* nocapture, i32, i32, i32, i32, i32, i32', 7),
        RESET: ('kp_reset_render_command', reset_helper(),
                '%struct._command_buffer_t addrspace(1)* nocapture, i32', 2),
    }
    expected = before
    for name, (replacement, body, signature, arity) in mappings.items():
        if '@' + name not in names:
            continue
        decl = re.findall(r'^declare void @' + re.escape(name) + r'\(' + re.escape(signature) +
                          r'\) local_unnamed_addr #\d+$', text, re.M)
        calls = re.findall(r'\bcall void @' + re.escape(name) + r'\(([^\n]+)\)', before)
        if len(decl) != 1 or not calls or len(calls) + 1 != names.count('@' + name):
            raise ValueError('Operation declaration/calls differ')
        for call in calls:
            args = call.split(', ')
            if len(args) != arity or not re.fullmatch(r'%struct\._command_buffer_t addrspace\(1\)\* nocapture %\w+', args[0]):
                raise ValueError('Command operands differ')
            if name == SET:
                if not re.fullmatch(r'i8 addrspace\(1\)\* %\w+', args[2]) or args[3] != 'i64 -1':
                    raise ValueError('Only ordinary device buffer with fixed stride is modelled')
                scalar = (args[1], args[4])
            else:
                if name == DRAW and args[2] != 'i32 3':
                    raise ValueError('Only literal triangles supported')
                scalar = args[1:]
            if any(not re.fullmatch(r'i32 (?:%\w+|-?\d+)', x) for x in scalar):
                raise ValueError('Scalar operand differs')
        text = text.replace(decl[0], body).replace('@' + name + '(', '@' + replacement + '(')
        expected = expected.replace('@' + name + '(', '@' + replacement + '(')
    text = rewrite_root(text)
    if entry_body(text) != expected or re.search(r'@air\.[\w.]*command[\w.]*', text):
        raise ValueError('Residual or changed command dataflow')
    return "; ModuleID = 'keplermetal-vertex-binding-experiment'\n" + text
