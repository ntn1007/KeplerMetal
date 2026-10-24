#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Preserve typed triangle-draw/reset dataflow using owned render records.

Offline translation is not shader qualification. Only literal triangles and
the existing single-root project ABI are accepted; indexed/resource setters
and other primitive types require another implementation and reception.
"""
import re
from lower_air_render_reset import normalized,helper
from air_reset_lowering import entry_body,rewrite_root

DRAW='air.draw_primitives_render_command'
RESET='air.reset_render_command'


def draw_helper():
    text=helper().replace('@kp_reset_render_command(', '@kp_draw_primitives_render_command(')
    text=text.replace('i32 %index) alwaysinline',
        'i32 %index, i32 %primitive, i32 %first, i32 %count, i32 %instances, i32 %base) alwaysinline')
    marker='  %record = inttoptr i64 %address to <4 x i32> addrspace(1)*'
    text=text.replace(marker,marker+'''
  %words = bitcast <4 x i32> addrspace(1)* %record to i32 addrspace(1)*
  %identityword = getelementptr i32, i32 addrspace(1)* %words, i64 8
  %identityptr = bitcast i32 addrspace(1)* %identityword to i64 addrspace(1)*
  %identity = load i64, i64 addrspace(1)* %identityptr, align 8''')
    stores=[]
    for i,value in enumerate(['1263555411','0','%count','%instances','%first','0','%base','0']):
        stores.extend([f'  %field{i} = getelementptr i32, i32 addrspace(1)* %words, i64 {i}',
                       f'  store i32 {value}, i32 addrspace(1)* %field{i}, align 4'])
    stores.append('  store i64 %identity, i64 addrspace(1)* %identityptr, align 8')
    text=text.replace('  br label %exit\nexit:', '\n'.join(stores)+'\n  br label %exit\nexit:')
    return text


def lower(ir):
    text=normalized(ir);before=entry_body(text)
    if '@kp_'in text:raise ValueError('Helper name collision')
    names=re.findall(r'@air\.[\w.]*command[\w.]*',text)
    if not names or set(names)-{'@'+DRAW,'@'+RESET}:raise ValueError('Unsupported command operation')
    if '@'+DRAW not in names:raise ValueError('A typed draw is required')
    mapping={DRAW:('kp_draw_primitives_render_command',draw_helper(),7),RESET:('kp_reset_render_command',helper(),2)}
    replacements={}
    for name,(replacement,body,arity)in mapping.items():
        if '@'+name not in names:continue
        args='%struct._command_buffer_t addrspace(1)* nocapture'+', i32'*(arity-1)
        pattern=r'^declare void @'+re.escape(name)+r'\('+re.escape(args)+r'\) local_unnamed_addr #\d+$'
        declarations=re.findall(pattern,text,re.M)
        calls=re.findall(r'\bcall void @'+re.escape(name)+r'\(([^\n]+)\)',before)
        if len(declarations)!=1 or not calls or len(calls)+1!=names.count('@'+name):raise ValueError('Command call/declaration differs')
        for call in calls:
            fields=call.split(', ')
            if len(fields)!=arity or not re.fullmatch(r'%struct\._command_buffer_t addrspace\(1\)\* nocapture %\w+',fields[0]):raise ValueError('Command operands differ')
            if name==DRAW and fields[2]!='i32 3':raise ValueError('Only literal triangle primitive is implemented')
            if any(not re.fullmatch(r'i32 (?:%\w+|-?\d+)',f)for f in fields[1:]):raise ValueError('Scalar command operands differ')
        text=text.replace(declarations[0],body).replace('@'+name+'(', '@'+replacement+'(')
        replacements['@'+name+'(']='@'+replacement+'('
    text=rewrite_root(text)
    expected=before
    for a,b in replacements.items():expected=expected.replace(a,b)
    if entry_body(text)!=expected:raise ValueError('Entry dataflow changed')
    if re.search(r'@air\.[\w.]*command[\w.]*',text):raise ValueError('Residual command operation')
    return "; ModuleID = 'keplermetal-typed-render-draw'\n"+text
