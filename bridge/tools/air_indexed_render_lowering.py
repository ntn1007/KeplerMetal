#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Lower typed 16/32-bit indexed triangles using owned, certified index spans.

Only known live context allocations are accepted. This is not a sandbox for
arbitrary GPU addresses. Index pointers are compared, never dereferenced here;
the existing materializer separately enforces complete draw-count bounds.
"""
import re
from lower_air_render_reset import normalized,helper as reset_helper
from air_reset_lowering import entry_body,rewrite_root

RESET='air.reset_render_command'
INDEXED={bits:f'air.draw_indexed_primitives_render_command.p1i{bits}'for bits in (16,32)}


def indexed_helper(bits):
    assert bits in (16,32)
    kind,shift=(1,1)if bits==16 else(2,2)
    text=reset_helper().split('  %q0 =')[0]
    text=text.replace('@kp_reset_render_command(',f'@kp_indexed_render_{bits}(')
    text=text.replace('i32 %index) alwaysinline',f'i32 %index, i32 %primitive, i32 %count, i{bits} addrspace(1)* %indices, i32 %instances, i32 %vertex, i32 %base) alwaysinline')
    text+='''  %words = bitcast <4 x i32> addrspace(1)* %record to i32 addrspace(1)*
  %idword = getelementptr i32, i32 addrspace(1)* %words, i64 8
  %idptr = bitcast i32 addrspace(1)* %idword to i64 addrspace(1)*
  %identity = load i64, i64 addrspace(1)* %idptr, align 8
  %noidentity = icmp eq i64 %identity, 0
  %ctxbytes = bitcast %struct._command_buffer_t addrspace(1)* %opaque to i8 addrspace(1)*
  %extbytes = getelementptr i8, i8 addrspace(1)* %ctxbytes, i64 32
  %ext = bitcast i8 addrspace(1)* %extbytes to {i32, i32, i32, i32, i64, i64} addrspace(1)*
'''
    for i,t in enumerate(['i32']*4+['i64']*2):
        text+=f'  %ep{i} = getelementptr {{i32, i32, i32, i32, i64, i64}}, {{i32, i32, i32, i32, i64, i64}} addrspace(1)* %ext, i32 0, i32 {i}\n  %e{i} = load {t}, {t} addrspace(1)* %ep{i}, align {4 if i<4 else 8}\n'
    text+='''  %emagic = icmp eq i32 %e0, 1263552856
  %eversion = icmp eq i32 %e1, 1
  %countlow = icmp ugt i32 %e2, 0
  %counthigh = icmp ule i32 %e2, 16
  %entrybytes = icmp eq i32 %e3, 48
  %ereserved = icmp eq i64 %e5, 0
  %ctxaddress = ptrtoint %struct._command_buffer_t addrspace(1)* %opaque to i64
  %expectedtable = add i64 %ctxaddress, 64
  %etable = icmp eq i64 %e4, %expectedtable
  %ext0 = and i1 %emagic, %eversion
  %ext1 = and i1 %countlow, %counthigh
  %ext2 = and i1 %entrybytes, %ereserved
  %ext3 = and i1 %ext0, %ext1
  %ext4 = and i1 %ext2, %etable
  %extok = and i1 %ext3, %ext4
  br i1 %extok, label %loop, label %refused
loop:
  %position = phi i32 [0, %reset], [%next, %advance]
  %position64 = zext i32 %position to i64
  %rowoffset = mul i64 %position64, 48
  %rowaddress = add i64 %e4, %rowoffset
  %row = inttoptr i64 %rowaddress to {i64, i64, i64, i32, i32, i32, i32, i64} addrspace(1)*
'''
    for i,t in enumerate(['i64']*3+['i32']*4+['i64']):
        text+=f'  %bp{i} = getelementptr {{i64, i64, i64, i32, i32, i32, i32, i64}}, {{i64, i64, i64, i32, i32, i32, i32, i64}} addrspace(1)* %row, i32 0, i32 {i}\n  %b{i} = load {t}, {t} addrspace(1)* %bp{i}, align {8 if t=="i64"else 4}\n'
    text+=f'''  %rowid = icmp ne i64 %b0, 0
  %sameid = icmp eq i64 %identity, %b0
  %idok = or i1 %sameid, %noidentity
  %slotok = icmp eq i32 %b3, %index
  %kindok = icmp eq i32 %b4, {kind}
  %rowreserved = icmp eq i32 %b6, 0
  %padding = icmp eq i64 %b7, 0
  %basevalid = icmp ugt i64 %b1, 0
  %baserange = icmp ult i64 %b1, 1099511627776
  %remainingaddress = sub i64 1099511627776, %b1
  %spanvalid = icmp ule i64 %b2, %remainingaddress
  %maxcount = zext i32 %b5 to i64
  %maxbytes = shl i64 %maxcount, {shift}
  %bytesmatch = icmp eq i64 %b2, %maxbytes
  %basebits = and i64 %b1, {(bits//8)-1}
  %basealigned = icmp eq i64 %basebits, 0
  %provided = ptrtoint i{bits} addrspace(1)* %indices to i64
  %pointerlow = icmp uge i64 %provided, %b1
  %difference = sub i64 %provided, %b1
  %pointerspan = icmp ule i64 %difference, %b2
  %pointerbits = and i64 %difference, {(bits//8)-1}
  %pointeraligned = icmp eq i64 %pointerbits, 0
  %match0 = and i1 %rowid, %idok
  %match1 = and i1 %slotok, %kindok
  %match2 = and i1 %rowreserved, %padding
  %match3 = and i1 %basevalid, %baserange
  %match4 = and i1 %spanvalid, %bytesmatch
  %match5 = and i1 %basealigned, %pointerlow
  %match6 = and i1 %pointerspan, %pointeraligned
  %match7 = and i1 %match0, %match1
  %match8 = and i1 %match2, %match3
  %match9 = and i1 %match4, %match5
  %match10 = and i1 %match7, %match8
  %match11 = and i1 %match9, %match6
  %matched = and i1 %match10, %match11
  br i1 %matched, label %write, label %advance
advance:
  %next = add nuw i32 %position, 1
  %more = icmp ult i32 %next, %e2
  br i1 %more, label %loop, label %refused
write:
  %first64 = lshr i64 %difference, {shift}
  %first = trunc i64 %first64 to i32
'''
    for i in range(4):text+=f'  %z{i} = getelementptr <4 x i32>, <4 x i32> addrspace(1)* %record, i64 {i}\n  store <4 x i32> zeroinitializer, <4 x i32> addrspace(1)* %z{i}, align 16\n'
    for i,value in enumerate(['1263555411',str(kind),'%count','%instances','%first','%vertex','%base','0']):text+=f'  %field{i} = getelementptr i32, i32 addrspace(1)* %words, i64 {i}\n  store i32 {value}, i32 addrspace(1)* %field{i}, align 4\n'
    text+='  store i64 %identity, i64 addrspace(1)* %idptr, align 8\n  br label %exit\nrefused:\n'
    for i in range(4):text+=f'  %r{i} = getelementptr <4 x i32>, <4 x i32> addrspace(1)* %record, i64 {i}\n  store <4 x i32> zeroinitializer, <4 x i32> addrspace(1)* %r{i}, align 16\n'
    return text+'  br label %exit\nexit:\n  ret void\n}'


def lower(ir):
    text=normalized(ir);before=entry_body(text)
    if '@kp_'in text:raise ValueError('Helper name collision')
    names=re.findall(r'@air\.[\w.]*command[\w.]*',text)
    allowed={'@'+RESET}|{'@'+n for n in INDEXED.values()}
    if not names or set(names)-allowed or not any('@'+n in names for n in INDEXED.values()):raise ValueError('Unsupported indexed command set')
    mappings={RESET:('kp_reset_render_command',reset_helper(),'%struct._command_buffer_t addrspace(1)* nocapture, i32',None)}
    for bits,name in INDEXED.items():mappings[name]=(f'kp_indexed_render_{bits}',indexed_helper(bits),f'%struct._command_buffer_t addrspace(1)* nocapture, i32, i32, i32, i{bits} addrspace(1)*, i32, i32, i32',bits)
    expected=before
    for name,(replacement,body,signature,bits)in mappings.items():
        if '@'+name not in names:continue
        decl=re.findall(r'^declare void @'+re.escape(name)+r'\('+re.escape(signature)+r'\) local_unnamed_addr #\d+$',text,re.M)
        calls=re.findall(r'\bcall void @'+re.escape(name)+r'\(([^\n]+)\)',before)
        if len(decl)!=1 or not calls or len(calls)+1!=names.count('@'+name):raise ValueError('Indexed operation declaration/calls differ')
        for call in calls:
            args=call.split(', ')
            if len(args)!=(8 if bits else 2)or not re.fullmatch(r'%struct\._command_buffer_t addrspace\(1\)\* nocapture %\w+',args[0]):raise ValueError('Indexed operands differ')
            if bits and(args[2]!='i32 3'or not re.fullmatch(r'i'+str(bits)+r' addrspace\(1\)\* %\w+',args[4])):raise ValueError('Only device typed indexed triangles are supported')
            for i,arg in enumerate(args[1:],1):
                if bits and i==4:continue
                if not re.fullmatch(r'i32 (?:%\w+|-?\d+)',arg):raise ValueError('Indexed scalar operand differs')
        text=text.replace(decl[0],body).replace('@'+name+'(', '@'+replacement+'(');expected=expected.replace('@'+name+'(', '@'+replacement+'(')
    text=rewrite_root(text)
    if entry_body(text)!=expected or re.search(r'@air\.[\w.]*command[\w.]*',text):raise ValueError('Residual or changed indexed dataflow')
    return "; ModuleID = 'keplermetal-indexed-render'\n"+text
