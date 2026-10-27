#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bounded typed fragment-buffer lowering, not an Apple ICB ABI or sandbox."""
import re
from lower_air_render_reset import normalized,helper as reset_helper
from air_reset_lowering import entry_body,rewrite_root
from air_render_draw_lowering import draw_helper,DRAW
from air_vertex_binding_lowering import setter_helper,EXT_MAGIC

SET='air.set_fragment_buffer_render_command.p1i8'
RESET='air.reset_render_command'
FRAGMENT_MAGIC=0x4b504658


def fragment_helper():
 text=setter_helper()
 changes={'@kp_set_vertex_buffer(':'@kp_set_fragment_buffer(',
          'i8 addrspace(1)* %buffer, i64 %stride, i32 %binding':'i8 addrspace(1)* %buffer, i32 %binding',
          '  %strideok = icmp eq i64 %stride, -1\n':'',
          '%ext3 = and i1 %etable, %strideok':'%ext3 = and i1 %etable, true',
          str(EXT_MAGIC):str(FRAGMENT_MAGIC)}
 for old,new in changes.items():
  if text.count(old)!=1:raise ValueError('Vertex helper structure differs')
  text=text.replace(old,new)
 return text


def lower(ir):
 text=normalized(ir);before=entry_body(text)
 if '@kp_' in text:raise ValueError('Helper collision')
 names=re.findall(r'@air\.[\w.]*command[\w.]*',text);allowed={'@'+SET,'@'+DRAW,'@'+RESET}
 if set(names)-allowed or '@'+SET not in names or '@'+DRAW not in names:raise ValueError('Expected typed fragment setter and triangle draw')
 mapping={SET:('kp_set_fragment_buffer',fragment_helper(),'%struct._command_buffer_t addrspace(1)* nocapture, i32, i8 addrspace(1)*, i32',4),
          DRAW:('kp_draw_primitives_render_command',draw_helper(),'%struct._command_buffer_t addrspace(1)* nocapture, i32, i32, i32, i32, i32, i32',7),
          RESET:('kp_reset_render_command',reset_helper(),'%struct._command_buffer_t addrspace(1)* nocapture, i32',2)}
 expected=before
 for name,(replacement,body,signature,arity) in mapping.items():
  if '@'+name not in names:continue
  decl=re.findall(r'^declare void @'+re.escape(name)+r'\('+re.escape(signature)+r'\) local_unnamed_addr #\d+$',text,re.M)
  calls=re.findall(r'\bcall void @'+re.escape(name)+r'\(([^\n]+)\)',before)
  if len(decl)!=1 or not calls or len(calls)+1!=names.count('@'+name):raise ValueError('Operation declarations/calls differ')
  for call in calls:
   args=call.split(', ')
   if len(args)!=arity or not re.fullmatch(r'%struct\._command_buffer_t addrspace\(1\)\* nocapture %\w+',args[0]):raise ValueError('Command operands differ')
   if name==SET:
    if not re.fullmatch(r'i8 addrspace\(1\)\* %\w+',args[2]):raise ValueError('Only device fragment buffers supported')
    scalar=(args[1],args[3])
   else:
    if name==DRAW and args[2]!='i32 3':raise ValueError('Only triangle primitives supported')
    scalar=args[1:]
   if any(not re.fullmatch(r'i32 (?:%\w+|-?\d+)',x)for x in scalar):raise ValueError('Scalar operand differs')
  text=text.replace(decl[0],body).replace('@'+name+'(', '@'+replacement+'(');expected=expected.replace('@'+name+'(', '@'+replacement+'(')
 text=rewrite_root(text)
 if entry_body(text)!=expected or re.search(r'@air\.[\w.]*command[\w.]*',text):raise ValueError('Residual or changed command dataflow')
 return "; ModuleID = 'keplermetal-fragment-binding-experiment'\n"+text
