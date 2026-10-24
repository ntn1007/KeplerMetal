#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bounded structural reset lowering. Offline transformation, not a GPU gate.

Execution still requires an independently qualified input and native program.
Only one root command resource at buffer zero is represented by this ABI.
"""
import re
from lower_air_render_reset import normalized,helper


def entry_body(ir):
    matches=re.findall(r'^define void @probe_boundary\([^\n]+\) [^\n]*\{\n(.*?)^\}',ir,re.M|re.S)
    if len(matches)!=1:raise ValueError('One ordinary probe entry required')
    return matches[0]


def lower(ir):
    text=normalized(ir);before=entry_body(text)
    pairs=re.findall(r'^!(\d+) = (.*)$',text,re.M);nodes=dict(pairs)
    if len(nodes)!=len(pairs):raise ValueError('Duplicate metadata node')
    roots=[(k,v)for k,v in nodes.items()if '!"air.indirect_buffer"'in v]
    if len(roots)!=1:raise ValueError('One indirect root required')
    root,value=roots[0]
    pattern=r'!\{i32 0, !"air.indirect_buffer", !"air.buffer_size", i32 8, !"air.location_index", i32 0, i32 1, !"air.read_write", !"air.address_space", i32 1, !"air.struct_type_info", !(\d+), !"air.arg_type_size", i32 8, !"air.arg_type_align_size", i32 8, !"air.arg_type_name", !"Arguments", !"air.arg_name", !"args"\}'
    m=re.fullmatch(pattern,value)
    if not m:raise ValueError('Root layout/binding differs')
    child=m[1];m=re.fullmatch(r'!\{i32 0, i32 8, i32 0, !"command_buffer", !"commands", !"air.indirect_argument", !(\d+)\}',nodes.get(child,''))
    if not m:raise ValueError('Root member differs')
    leaf=m[1]
    if nodes.get(leaf)!='!{i32 0, !"air.command_buffer", !"air.location_index", i32 0, i32 1, !"air.arg_type_name", !"command_buffer", !"air.arg_name", !"commands"}':raise ValueError('Command leaf differs')
    for n in [child,leaf]:
        if len(re.findall(r'!'+n+r'(?!\d)',text))!=2:raise ValueError('Shared command metadata refused')
    if '%struct.Arguments = type { %"struct.metal::command_buffer" }'not in text:raise ValueError('Root LLVM layout differs')
    decl='declare void @air.reset_render_command(%struct._command_buffer_t addrspace(1)* nocapture, i32) local_unnamed_addr #1'
    if text.count(decl)!=1 or len(re.findall(r'@air\.reset_render_command\(',before))!=1:raise ValueError('One reset operation required')
    names=re.findall(r'@air\.[\w.]*command[\w.]*',text)
    if names!=['@air.reset_render_command','@air.reset_render_command']:raise ValueError('Other command operations refused')
    if '@kp_reset_render_command'in text:raise ValueError('Helper collision')
    text=text.replace(decl,helper()).replace('@air.reset_render_command(', '@kp_reset_render_command(')
    descriptor='!{i32 0, !"air.buffer", !"air.buffer_size", i32 8, !"air.location_index", i32 0, i32 1, !"air.read", !"air.address_space", i32 1, !"air.arg_type_size", i32 8, !"air.arg_type_align_size", i32 8, !"air.arg_type_name", !"ulong", !"air.arg_name", !"project_root"}'
    text=re.sub(r'^!'+root+r' = .*$', '!'+root+' = '+descriptor,text,flags=re.M)
    for n in [child,leaf]:text=re.sub(r'^!'+n+r' = .*\n','',text,flags=re.M)
    if 'air.indirect_buffer'in text or 'air.command_buffer'in text:raise ValueError('Residual command metadata')
    if entry_body(text)!=before.replace('@air.reset_render_command(', '@kp_reset_render_command('):raise ValueError('Entry dataflow changed')
    return "; ModuleID = 'keplermetal-structural-reset'\n"+text
