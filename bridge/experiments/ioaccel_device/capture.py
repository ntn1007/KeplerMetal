#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read bounded loaded IOAccelerator entry bytes; call none of the entries."""
import ctypes,hashlib,json,os,platform,struct,sys
from pathlib import Path
PATH='/System/Library/PrivateFrameworks/IOAccelerator.framework/Versions/A/IOAccelerator'
NAMES=('IOAccelDeviceGetConfig','IOAccelDeviceCreate','IOAccelDeviceRelease')
EXPECTED='1f97e27b78826a4c4801f851173d67e97d00f7b1668fe5882e19895eb74b9ece'
class Info(ctypes.Structure):_fields_=[('path',ctypes.c_char_p),('base',ctypes.c_void_p),('symbol',ctypes.c_char_p),('address',ctypes.c_void_p)]
def require(value,message):
 if not value:raise ValueError(message)
def uuid_at(base):
 header=ctypes.string_at(base,32);magic,cpu,_,_,count,size,_,_=struct.unpack('<8I',header)
 require(magic==0xfeedfacf and cpu==0x1000007 and count<4096 and size<1048576,'Unexpected image header')
 commands=ctypes.string_at(base+32,size);pos=0;uuids=[]
 for _ in range(count):
  require(pos+8<=size,'Truncated image command');kind,length=struct.unpack_from('<II',commands,pos)
  require(length>=8 and pos+length<=size,'Invalid image command')
  if kind==0x1b:
   require(length==24,'Invalid UUID');uuids.append(commands[pos+8:pos+24].hex())
  pos+=length
 require(pos==size and len(uuids)==1,'Image UUID unavailable');return uuids[0]
def run(out):
 require(platform.system()=='Darwin' and platform.machine()=='x86_64' and os.getuid()!=0,'Unexpected host')
 require(not out.exists() and out.parent.is_dir(),'Fresh directory required');out.mkdir()
 system=ctypes.CDLL('/usr/lib/libSystem.B.dylib');system.dladdr.argtypes=[ctypes.c_void_p,ctypes.POINTER(Info)];system.dladdr.restype=ctypes.c_int
 lib=ctypes.CDLL(PATH,mode=ctypes.RTLD_LOCAL);rows=[];base=None;getaddr=None
 for name in NAMES:
  f=getattr(lib,name);addr=ctypes.cast(f,ctypes.c_void_p).value;info=Info()
  require(system.dladdr(addr,ctypes.byref(info)) and info.path and info.path.decode()==PATH and info.base and info.address==addr,'Unqualified exported symbol')
  require(base is None or info.base==base,'Inconsistent image');base=info.base
  require((addr&4095)+256<=4096,'Entry crosses page boundary')
  code=ctypes.string_at(addr,256);(out/(name+'.private.bin')).write_bytes(code)
  rows.append({'name':name,'image_offset':addr-base,'bytes':len(code),'entry_sha256':hashlib.sha256(code).hexdigest()})
  if name=='IOAccelDeviceGetConfig':getaddr=addr
 image_uuid=uuid_at(base);require(image_uuid=='198a776afe0335ee8e537b9f14caabaa','IOAccelerator image UUID changed')
 code=(out/'IOAccelDeviceGetConfig.private.bin').read_bytes()
 require(hashlib.sha256(code).hexdigest()==EXPECTED and code[0x2f]==0xe8,'Unqualified configuration function')
 stub=getaddr+0x34+struct.unpack_from('<i',code,0x30)[0];si=Info()
 require(system.dladdr(stub,ctypes.byref(si)) and si.base==base,'Call target outside image')
 insn=ctypes.string_at(stub,6);require(insn[:2]==b'\xff\x25','Unqualified stub')
 got=stub+6+struct.unpack_from('<i',insn,2)[0];resolved=ctypes.c_void_p.from_address(got).value;ri=Info()
 require(resolved and system.dladdr(resolved,ctypes.byref(ri)) and ri.path and ri.symbol and ri.symbol.decode()=='CFGetTypeID' and ri.address==resolved,'Unexpected resolved type query')
 result={'status':'PASS','image_UUID':image_uuid,'functions':rows,'type_query':{'resolved_symbol':'CFGetTypeID','owner':ri.path.decode(),'exact_symbol':True,'function_called':False},'function_calls_made':False,'gpu_commands_submitted':False,'library_initializers_may_run':True,'code_bytes_distributed':False,'capture_source_SHA256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
 (out/'metadata.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':run(Path(sys.argv[1]).resolve())
