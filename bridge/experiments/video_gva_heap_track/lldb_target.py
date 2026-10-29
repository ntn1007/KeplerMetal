# SPDX-License-Identifier: MIT
"""Only write the exported watcher slot in the controlled own-process library."""
import struct
import lldb


def symbol(target,name):
    found=target.FindSymbols(name)
    if found.GetSize()!=1:return None
    obj=found.GetContextAtIndex(0).GetSymbol()
    if not obj.IsValid():return None
    value=obj.GetStartAddress().GetLoadAddress(target)
    return value if value and value != lldb.LLDB_INVALID_ADDRESS else None


def read(process,address,size):
    err=lldb.SBError();data=process.ReadMemory(address,size,err)
    return data if err.Success() and len(data)==size else None


def set_target(process,address,pointer):
    if read(process,address,8)!=struct.pack('<Q',1) or not pointer:return False
    err=lldb.SBError();size=process.WriteMemory(address,struct.pack('<Q',pointer),err)
    return err.Success() and size==8 and read(process,address,8)==struct.pack('<Q',pointer)
