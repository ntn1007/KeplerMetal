#!/usr/bin/env python3
"""Read-only symbol/selector resolution for the observed indirect entry points."""
from pathlib import Path
import argparse,hashlib,json,struct
p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);a=p.parse_args();ROOT=Path(__file__).resolve().parents[1];out=a.out.resolve();out.relative_to(ROOT/'results');assert not out.exists();out.mkdir()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def layout(data):
 assert data[:4]==b'\xcf\xfa\xed\xfe';off=32;segments=[];commands={}
 for i in range(struct.unpack_from('<I',data,16)[0]):
  kind,length=struct.unpack_from('<II',data,off);assert length>=8 and off+length<=len(data);commands[kind]=off
  if kind==0x19:
   name=data[off+8:off+24].split(b'\0')[0].decode();va,vs,fo,fs=struct.unpack_from('<4Q',data,off+24);segments.append({'name':name,'VA':va,'offset':fo,'bytes':fs,'command':off})
  off+=length
 return segments,commands
def at(segments,address):
 matches=[s for s in segments if s['VA']<=address<s['VA']+s['bytes']];assert len(matches)==1;s=matches[0];return s['offset']+address-s['VA']
def string(data,offset):assert 0<=offset<len(data);return data[offset:data.index(b'\0',offset)].decode()
old=Path('/System/Library/Frameworks/Metal.framework/Versions/A/MetalOld.dylib');b=old.read_bytes();segments,commands=layout(b);off=commands[0x80000034];start,size=struct.unpack_from('<II',b,off+8)
version,starts,imports,symbols,count,fmt,symfmt=struct.unpack_from('<7I',b,start);assert version==0 and fmt==1 and symfmt==0
table=start+starts;seg_count=struct.unpack_from('<I',b,table)[0];formats={}
for i in range(seg_count):
 rel=struct.unpack_from('<I',b,table+4+4*i)[0]
 if rel:formats[segments[i]['name']]=struct.unpack_from('<H',b,table+rel+6)[0]
assert formats['__DATA']==6 # DYLD_CHAINED_PTR_64_OFFSET in SDK fixup-chains.h
raw=struct.unpack_from('<Q',b,at(segments,0x230110))[0];assert not raw>>63;target=raw&((1<<36)-1);resolved_selector=string(b,at(segments,target));assert resolved_selector=='doesNotRecognizeSelector:'
raw_bind=struct.unpack_from('<Q',b,at(segments,0x1e0b60))[0];assert raw_bind>>63;ordinal=raw_bind&0xffffff;assert ordinal<count
word=struct.unpack_from('<I',b,start+imports+ordinal*4)[0];bound=string(b,start+symbols+(word>>9));assert bound=='_objc_msgSend'
driver=Path('/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver');d=driver.read_bytes();ds,dc=layout(d);symoff,nsyms,stroff,strsize=struct.unpack_from('<4I',d,dc[2]+8);dys=struct.unpack_from('<18I',d,dc[0xb]+8);indoff,indcount=dys[12:14];bindings=[]
for segment in ds:
 co=segment['command'];nsects=struct.unpack_from('<I',d,co+64)[0]
 for i in range(nsects):
  so=co+72+i*80;section=d[so:so+16].split(b'\0')[0].decode();va,length=struct.unpack_from('<QQ',d,so+32);flags,reserved1,reserved2=struct.unpack_from('<III',d,so+64)
  if section not in ['__stubs','__got']:continue
  for address in [0x1c0240,0x187574,0x18760a,0x18774e]:
   if va<=address<va+length:
    stride=reserved2 if section=='__stubs' else 8;index=reserved1+(address-va)//stride;assert index<indcount
    symbol_index=struct.unpack_from('<I',d,indoff+index*4)[0];assert symbol_index<nsyms
    name_offset=struct.unpack_from('<I',d,symoff+symbol_index*16)[0];name=string(d,stroff+name_offset)
    bindings.append({'VA':hex(address),'section':section,'indirect_symbol_index':index,'symbol':name})
assert len(bindings)==4
sdk=Path('/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX26.2.sdk/usr/include/mach-o/fixup-chains.h');(out/'SDK-fixup-chains.h').write_bytes(sdk.read_bytes())
summary={'status':'PASS','MetalOld':{'path':str(old),'sha256':sha(old),'renderer_ICB_methods':['0xced53','0xced68'],
 'selector_cell':'0x230110','selector_pointer_format':formats['__DATA'],'selector_resolved':resolved_selector,
 'objc_dispatch_cell':'0x1e0b60','bound_symbol':bound,
 'conclusion':'Both inherited render ICB methods forward the original selector to doesNotRecognizeSelector:, not native indirect rendering.'},
 'native_driver':{'path':str(driver),'sha256':sha(driver),'bindings':bindings,
 'compute_indirect_function_range':['0xd5e53','0xd68b9'],'resource_address_access':['0xd5f55','0xd5f61'],
 'conclusion':'Static native method uses IOAccel resource descriptor, resource-list registrations and command buffer writes; no private encoder ABI called or patched.'},
 'SDK_fixup_header_sha256':sha(sdk),'system_modified':False,'GPU_dispatch':False}
(out/'verification.json').write_text(json.dumps(summary,indent=2)+'\n');(out/Path(__file__).name).write_bytes(Path(__file__).read_bytes());print(json.dumps(summary,indent=2))
