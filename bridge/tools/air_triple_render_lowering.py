#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bounded indexed, vertex and pipeline command lowering for a triple context.

Only certified allocations may be dispatched. This is not an Apple ICB ABI
or an arbitrary GPU-pointer sandbox. Other operation shapes are refused.
"""
import re
from lower_air_render_reset import normalized, helper as reset_helper
from air_reset_lowering import entry_body
from air_indexed_render_lowering import indexed_helper, INDEXED, RESET
from air_vertex_binding_lowering import SET as VERTEX
from air_combined_index_vertex_lowering import combined_setter_helper
from air_pipeline_binding_lowering import SET as PIPELINE, rewrite_pipeline_root, PIPELINE_MAGIC


def pipeline_helper():
    text=combined_setter_helper()
    changes={
      '@kp_set_vertex_buffer(': '@kp_set_render_pipeline(',
      'i8 addrspace(1)* %buffer, i64 %stride, i32 %binding': '%struct._render_pipeline_state_t addrspace(1)* %pipeline',
      'ptrtoint i8 addrspace(1)* %buffer to i64': 'ptrtoint %struct._render_pipeline_state_t addrspace(1)* %pipeline to i64',
      '  %strideok = icmp eq i64 %stride, -1\n':'',
      '%vx3 = and i1 %vtableok, %strideok':'%vx3 = and i1 %vtableok, true',
      '%bindingok = icmp eq i32 %b4, %binding':'%bindingok = icmp eq i32 %b4, 0',
      '%position = phi i32 [0, %vertex_header], [%next, %advance]':'%position = phi i32 [0, %pipeline_header], [%next, %advance]',
      '%rowaddress = add i64 %ve4, %rowoffset':'%rowaddress = add i64 %pe4, %rowoffset',
      '%more = icmp ult i32 %next, %ve2':'%more = icmp ult i32 %next, %pe2',
    }
    for old,new in changes.items():
        if text.count(old)!=1:raise ValueError('Unexpected combined helper shape')
        text=text.replace(old,new)
    header='''  br i1 %vok, label %pipeline_header, label %refused
pipeline_header:
  %vertexcount64 = zext i32 %ve2 to i64
  %vertexbytes = mul i64 %vertexcount64, 32
  %pipelineaddress = add i64 %ve4, %vertexbytes
  %pipelineheader = inttoptr i64 %pipelineaddress to {i32, i32, i32, i32, i64, i64} addrspace(1)*
'''
    for i,t in enumerate(['i32']*4+['i64']*2):
        header+=(f'  %pp{i} = getelementptr {{i32, i32, i32, i32, i64, i64}}, '
                 f'{{i32, i32, i32, i32, i64, i64}} addrspace(1)* %pipelineheader, i32 0, i32 {i}\n'
                 f'  %pe{i} = load {t}, {t} addrspace(1)* %pp{i}, align {4 if i<4 else 8}\n')
    header+=f'''  %pmagic = icmp eq i32 %pe0, {PIPELINE_MAGIC}
  %pversion = icmp eq i32 %pe1, 1
  %pcountlow = icmp ugt i32 %pe2, 0
  %pcounthigh = icmp ule i32 %pe2, 64
  %pbytes = icmp eq i32 %pe3, 32
  %preserved = icmp eq i64 %pe5, 0
  %pexpected = add i64 %pipelineaddress, 32
  %ptableok = icmp eq i64 %pe4, %pexpected
  %pk0 = and i1 %pmagic, %pversion
  %pk1 = and i1 %pcountlow, %pcounthigh
  %pk2 = and i1 %pbytes, %preserved
  %pk3 = and i1 %pk0, %pk1
  %pk4 = and i1 %pk2, %ptableok
  %pok = and i1 %pk3, %pk4
  br i1 %pok, label %loop, label %refused'''
    old='  br i1 %vok, label %loop, label %refused'
    if text.count(old)!=1:raise ValueError('Vertex header branch differs')
    return text.replace(old,header)


def lower(ir):
    text=normalized(ir);before=entry_body(text)
    if '@kp_' in text:raise ValueError('Helper collision')
    names=re.findall(r'@air\.[\w.]*command[\w.]*',text)
    allowed={'@'+VERTEX,'@'+PIPELINE,'@'+RESET}|{'@'+n for n in INDEXED.values()}
    if set(names)-allowed or '@'+VERTEX not in names or '@'+PIPELINE not in names or not all('@'+n in names for n in INDEXED.values()):
        raise ValueError('Expected pipeline, vertex and both indexed operations')
    mapping={VERTEX:('kp_set_vertex_buffer',combined_setter_helper(),'%struct._command_buffer_t addrspace(1)* nocapture, i32, i8 addrspace(1)*, i64, i32','vertex'),
             PIPELINE:('kp_set_render_pipeline',pipeline_helper(),'%struct._command_buffer_t addrspace(1)* nocapture, i32, %struct._render_pipeline_state_t addrspace(1)* readonly','pipeline'),
             RESET:('kp_reset_render_command',reset_helper(),'%struct._command_buffer_t addrspace(1)* nocapture, i32',None)}
    for bits,name in INDEXED.items():mapping[name]=(f'kp_indexed_render_{bits}',indexed_helper(bits),f'%struct._command_buffer_t addrspace(1)* nocapture, i32, i32, i32, i{bits} addrspace(1)*, i32, i32, i32',bits)
    expected=before
    for name,(replacement,body,signature,kind) in mapping.items():
        if '@'+name not in names:continue
        decl=re.findall(r'^declare void @'+re.escape(name)+r'\('+re.escape(signature)+r'\) local_unnamed_addr #\d+$',text,re.M)
        calls=re.findall(r'\bcall void @'+re.escape(name)+r'\(([^\n]+)\)',before)
        if len(decl)!=1 or not calls or len(calls)+1!=names.count('@'+name):raise ValueError('Operation declaration/calls differ')
        for call in calls:
            args=call.split(', ');arity=5 if kind=='vertex' else 3 if kind=='pipeline' else 8 if kind else 2
            if len(args)!=arity or not re.fullmatch(r'%struct\._command_buffer_t addrspace\(1\)\* nocapture %\w+',args[0]):raise ValueError('Command operands differ')
            if kind=='vertex':
                if not re.fullmatch(r'i8 addrspace\(1\)\* %\w+',args[2]) or args[3]!='i64 -1':raise ValueError('Only fixed-stride device buffers supported')
                scalar=(args[1],args[4])
            elif kind=='pipeline':
                if not re.fullmatch(r'%struct\._render_pipeline_state_t addrspace\(1\)\* readonly %\w+',args[2]):raise ValueError('Pipeline operand differs')
                scalar=args[1:2]
            elif kind:
                if args[2]!='i32 3' or not re.fullmatch(r'i'+str(kind)+r' addrspace\(1\)\* %\w+',args[4]):raise ValueError('Only device indexed triangles supported')
                scalar=args[1:4]+args[5:]
            else:scalar=args[1:]
            if any(not re.fullmatch(r'i32 (?:%\w+|-?\d+)',x) for x in scalar):raise ValueError('Scalar operand differs')
        text=text.replace(decl[0],body).replace('@'+name+'(', '@'+replacement+'(');expected=expected.replace('@'+name+'(', '@'+replacement+'(')
    text=rewrite_pipeline_root(text)
    if entry_body(text)!=expected or re.search(r'@air\.[\w.]*command[\w.]*',text):raise ValueError('Residual or changed command dataflow')
    return "; ModuleID = 'keplermetal-triple-render-experiment'\n"+text
