#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exact-profile AIR lowering, not an arbitrary LLVM/Metal translator.

The input shader is unchanged. Its caller must supply the explicit project
context described below, rather than an Apple indirect command resource.
"""
import hashlib
import re

PROFILE = 'typed-render-reset-air28-v1'
FUNCTION = 'probe_boundary'
AIR_SHA256 = '4a6b0daed0ffc4437759d773725df3259e2354368e488c80176562af213f74ee'
IR_SHA256 = '7601d733e31ab69f05bdf7a776eaaa6013abf1f7c186423972e5e0d419abba0b'
MAGIC = 0x4b505243
CONTEXT_BYTES = 32
RECORD_BYTES = 64
MAX_CAPACITY = 16


def normalized(ir):
    if not isinstance(ir, str) or len(ir) > 65536:
        raise ValueError('Bounded textual AIR required')
    lines = ir.splitlines()
    if not lines or not re.fullmatch(r"; ModuleID = '[^\r\n']+'", lines[0]):
        raise ValueError('Unexpected module identifier')
    return '\n'.join(lines[1:]) + '\n'


def lower(ir):
    text = normalized(ir)
    if hashlib.sha256(text.encode()).hexdigest() != IR_SHA256:
        raise ValueError('Unqualified AIR profile; input left unchanged')
    call = 'declare void @air.reset_render_command(%struct._command_buffer_t addrspace(1)* nocapture, i32) local_unnamed_addr #1'
    if text.count(call) != 1:
        raise ValueError('Operation declaration differs')
    text = text.replace(call, helper())
    text = text.replace('@air.reset_render_command(', '@kp_reset_render_command(')
    # Keep the original LLVM argument/load and entry body. Only resource
    # description changes: an ordinary eight-byte project root, not an ICB.
    text = re.sub(r'^!18 = .*$', '!18 = !{i32 0, !"air.buffer", !"air.buffer_size", i32 8, !"air.location_index", i32 0, i32 1, !"air.read", !"air.address_space", i32 1, !"air.arg_type_size", i32 8, !"air.arg_type_align_size", i32 8, !"air.arg_type_name", !"ulong", !"air.arg_name", !"project_root"}', text, flags=re.M)
    text = re.sub(r'^!(19|20) = .*\n', '', text, flags=re.M)
    if 'air.command_buffer' in text or 'air.indirect_buffer' in text or '@air.reset_render_command' in text:
        raise ValueError('Unlowered command semantics')
    return '; ModuleID = \'keplermetal-render-reset\'\n' + text


def helper():
    # Root pointer MUST refer to a live allocated 32-byte project context.
    # Header rejection is not a sandbox for arbitrary GPU addresses.
    lines = ['''define internal void @kp_reset_render_command(%struct._command_buffer_t addrspace(1)* %opaque, i32 %index) alwaysinline nounwind {
entry:
  %nonnull = icmp ne %struct._command_buffer_t addrspace(1)* %opaque, null
  br i1 %nonnull, label %header, label %exit
header:
  %ctx = bitcast %struct._command_buffer_t addrspace(1)* %opaque to {i32, i32, i32, i32, i64, i64} addrspace(1)*''']
    for i, kind in enumerate(['i32']*4+['i64']*2):
        lines += [f'  %p{i} = getelementptr {{i32, i32, i32, i32, i64, i64}}, {{i32, i32, i32, i32, i64, i64}} addrspace(1)* %ctx, i32 0, i32 {i}',
                  f'  %v{i} = load {kind}, {kind} addrspace(1)* %p{i}, align {4 if i<4 else 8}']
    lines += [f'''  %magic = icmp eq i32 %v0, {MAGIC}
  %version = icmp eq i32 %v1, 1
  %caplow = icmp ugt i32 %v2, 0
  %caphigh = icmp ule i32 %v2, 16
  %size = icmp eq i32 %v3, 64
  %reserved = icmp eq i64 %v5, 0
  %indexok = icmp ult i32 %index, %v2
  %addresslow = icmp ugt i64 %v4, 0
  %addresshigh = icmp ule i64 %v4, 1099511626752
  %alignmentbits = and i64 %v4, 15
  %alignment = icmp eq i64 %alignmentbits, 0
  %ok0 = and i1 %magic, %version
  %ok1 = and i1 %caplow, %caphigh
  %ok2 = and i1 %size, %reserved
  %ok3 = and i1 %indexok, %addresslow
  %ok4 = and i1 %addresshigh, %alignment
  %ok5 = and i1 %ok0, %ok1
  %ok6 = and i1 %ok2, %ok3
  %ok7 = and i1 %ok5, %ok6
  %ok = and i1 %ok7, %ok4
  br i1 %ok, label %reset, label %exit
reset:
  %wide = zext i32 %index to i64
  %offset = shl i64 %wide, 6
  %address = add i64 %v4, %offset
  %record = inttoptr i64 %address to <4 x i32> addrspace(1)*''']
    for i in range(4):
        lines += [f'  %q{i} = getelementptr <4 x i32>, <4 x i32> addrspace(1)* %record, i64 {i}',
                  f'  store <4 x i32> zeroinitializer, <4 x i32> addrspace(1)* %q{i}, align 16']
    lines += ['  br label %exit', 'exit:', '  ret void', '}']
    return '\n'.join(lines)
