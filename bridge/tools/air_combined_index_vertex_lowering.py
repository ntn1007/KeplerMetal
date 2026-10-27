#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Lower typed vertex setters and indexed draws against an owned dual context.

This is a bounded project ABI, not an Apple ICB implementation or pointer
sandbox. Execution requires certified native code and retained Metal resources.
"""
import re
from lower_air_render_reset import normalized, helper as reset_helper
from air_reset_lowering import entry_body, rewrite_root
from air_indexed_render_lowering import indexed_helper, INDEXED, RESET
from air_vertex_binding_lowering import setter_helper, SET


def combined_setter_helper():
    base=setter_helper()
    start=base.index('  %emagic =')
    end=base.index('loop:\n',start)
    check='''  %imagic = icmp eq i32 %e0, 1263552856
  %iversion = icmp eq i32 %e1, 1
  %icountlow = icmp ugt i32 %e2, 0
  %icounthigh = icmp ule i32 %e2, 16
  %ibytes = icmp eq i32 %e3, 48
  %ireserved = icmp eq i64 %e5, 0
  %ctxaddress = ptrtoint %struct._command_buffer_t addrspace(1)* %opaque to i64
  %indexexpected = add i64 %ctxaddress, 64
  %itable = icmp eq i64 %e4, %indexexpected
  %i0 = and i1 %imagic, %iversion
  %i1 = and i1 %icountlow, %icounthigh
  %i2 = and i1 %ibytes, %ireserved
  %i3 = and i1 %i0, %i1
  %i4 = and i1 %i2, %itable
  %iok = and i1 %i3, %i4
  br i1 %iok, label %vertex_header, label %refused
vertex_header:
  %indexcount64 = zext i32 %e2 to i64
  %indexbytes = mul i64 %indexcount64, 48
  %vertexaddress = add i64 %e4, %indexbytes
  %vertexheader = inttoptr i64 %vertexaddress to {i32, i32, i32, i32, i64, i64} addrspace(1)*
'''
    for i,t in enumerate(['i32']*4+['i64']*2):
        check+=(f'  %vp{i} = getelementptr {{i32, i32, i32, i32, i64, i64}}, '
                f'{{i32, i32, i32, i32, i64, i64}} addrspace(1)* %vertexheader, i32 0, i32 {i}\n'
                f'  %ve{i} = load {t}, {t} addrspace(1)* %vp{i}, align {4 if i<4 else 8}\n')
    check+='''  %vmagic = icmp eq i32 %ve0, 1263556184
  %vversion = icmp eq i32 %ve1, 1
  %vcountlow = icmp ugt i32 %ve2, 0
  %vcounthigh = icmp ule i32 %ve2, 64
  %vbytes = icmp eq i32 %ve3, 32
  %vreserved = icmp eq i64 %ve5, 0
  %vexpected = add i64 %vertexaddress, 32
  %vtableok = icmp eq i64 %ve4, %vexpected
  %strideok = icmp eq i64 %stride, -1
  %provided = ptrtoint i8 addrspace(1)* %buffer to i64
  %bufferlow = icmp ugt i64 %provided, 0
  %bufferhigh = icmp ult i64 %provided, 1099511627776
  %v0 = and i1 %vmagic, %vversion
  %v1 = and i1 %vcountlow, %vcounthigh
  %v2 = and i1 %vbytes, %vreserved
  %v3 = and i1 %vtableok, %strideok
  %v4 = and i1 %bufferlow, %bufferhigh
  %v5 = and i1 %v0, %v1
  %v6 = and i1 %v2, %v3
  %v7 = and i1 %v5, %v6
  %vok = and i1 %v7, %v4
  br i1 %vok, label %loop, label %refused
'''
    for i in range(8):check=re.sub(r'%v'+str(i)+r'(?![0-9])','%vx'+str(i),check)
    result=base[:start]+check+base[end:]
    result=result.replace('%position = phi i32 [0, %reset], [%next, %advance]', '%position = phi i32 [0, %vertex_header], [%next, %advance]')
    result=result.replace('%rowaddress = add i64 %e4, %rowoffset', '%rowaddress = add i64 %ve4, %rowoffset')
    result=result.replace('%more = icmp ult i32 %next, %e2', '%more = icmp ult i32 %next, %ve2')
    return result


def lower(ir):
    text=normalized(ir);before=entry_body(text)
    if '@kp_' in text:raise ValueError('Helper name collision')
    names=re.findall(r'@air\.[\w.]*command[\w.]*',text)
    allowed={'@'+SET,'@'+RESET}|{'@'+n for n in INDEXED.values()}
    if not names or set(names)-allowed or '@'+SET not in names or not any('@'+n in names for n in INDEXED.values()):
        raise ValueError('Expected typed vertex and indexed operations only')
    mapping={SET:('kp_set_vertex_buffer',combined_setter_helper(),'%struct._command_buffer_t addrspace(1)* nocapture, i32, i8 addrspace(1)*, i64, i32','vertex'),
             RESET:('kp_reset_render_command',reset_helper(),'%struct._command_buffer_t addrspace(1)* nocapture, i32',None)}
    for bits,name in INDEXED.items():mapping[name]=(f'kp_indexed_render_{bits}',indexed_helper(bits),f'%struct._command_buffer_t addrspace(1)* nocapture, i32, i32, i32, i{bits} addrspace(1)*, i32, i32, i32',bits)
    expected=before
    for name,(replacement,body,signature,kind) in mapping.items():
        if '@'+name not in names:continue
        decl=re.findall(r'^declare void @'+re.escape(name)+r'\('+re.escape(signature)+r'\) local_unnamed_addr #\d+$',text,re.M)
        calls=re.findall(r'\bcall void @'+re.escape(name)+r'\(([^\n]+)\)',before)
        if len(decl)!=1 or not calls or len(calls)+1!=names.count('@'+name):raise ValueError('Operation declaration/calls differ')
        for call in calls:
            args=call.split(', ');arity=5 if kind=='vertex' else 8 if kind else 2
            if len(args)!=arity or not re.fullmatch(r'%struct\._command_buffer_t addrspace\(1\)\* nocapture %\w+',args[0]):raise ValueError('Command operands differ')
            if kind=='vertex':
                if not re.fullmatch(r'i8 addrspace\(1\)\* %\w+',args[2]) or args[3]!='i64 -1':raise ValueError('Only fixed-stride device buffer supported')
                scalar=(args[1],args[4])
            elif kind:
                if args[2]!='i32 3' or not re.fullmatch(r'i'+str(kind)+r' addrspace\(1\)\* %\w+',args[4]):raise ValueError('Only device indexed triangles supported')
                scalar=args[1:4]+args[5:]
            else:scalar=args[1:]
            if any(not re.fullmatch(r'i32 (?:%\w+|-?\d+)',x) for x in scalar):raise ValueError('Scalar operand differs')
        text=text.replace(decl[0],body).replace('@'+name+'(', '@'+replacement+'(');expected=expected.replace('@'+name+'(', '@'+replacement+'(')
    text=rewrite_root(text)
    if entry_body(text)!=expected or re.search(r'@air\.[\w.]*command[\w.]*',text):raise ValueError('Residual or changed command dataflow')
    return "; ModuleID = 'keplermetal-combined-index-vertex'\n"+text
