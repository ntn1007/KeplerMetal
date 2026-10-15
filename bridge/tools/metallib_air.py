#!/usr/bin/env python3
"""Bounded indexed AIR extraction; never scan blindly for bitcode magic."""
import hashlib,struct
class MetallibError(ValueError):pass
def sha(data):return hashlib.sha256(data).hexdigest()
def indexed_modules(data):
 if len(data)<88 or len(data)>64*1024*1024 or data[:4]!=b'MTLB':raise MetallibError('Only a bounded thin MTLB AIR container is currently qualified')
 def u64(o):return struct.unpack_from('<Q',data,o)[0]
 if u64(16)!=len(data):raise MetallibError('Declared library length differs')
 sections=[]
 for offset in [24,40,56,72]:
  start,length=u64(offset),u64(offset+8)
  if start<88 or start>len(data) or length>len(data)-start:raise MetallibError('Section outside library')
  sections.append((start,length))
 for i,(start,length) in enumerate(sections):
  if i==0:
   if length>len(data)-start-8:raise MetallibError('Function-list count/terminator outside library')
   length+=8
  for other,other_length in sections[i+1:]:
   if length and other_length and max(start,other)<min(start+length,other+other_length):raise MetallibError('Overlapping sections')
 start,length=sections[0];limit=start+length
 if length<4:raise MetallibError('Missing function count')
 count=struct.unpack_from('<I',data,start)[0]
 if not 1<=count<=1024 or count>(length-4)//8:raise MetallibError('Unqualified function count')
 position=start+4;modules=[];names=set();bc,bc_length=sections[3]
 for index in range(count):
  if position+4>limit:raise MetallibError('Truncated entry')
  entry_size=struct.unpack_from('<I',data,position)[0];end=position+entry_size
  # Compiler function-list length excludes its leading count. The final ENDT
  # may therefore occupy the four bytes immediately following this section.
  if entry_size<8 or end>limit+4 or end>len(data):raise MetallibError('Invalid entry length')
  tag_position=position+4;tags={};ended=False
  while tag_position+4<=end:
   tag=data[tag_position:tag_position+4]
   if tag==b'ENDT':
    if tag_position+4!=end:raise MetallibError('Unexpected bytes after entry terminator')
    ended=True;break
   if tag_position+6>end:raise MetallibError('Truncated tag length')
   size=struct.unpack_from('<H',data,tag_position+4)[0];payload=tag_position+6
   if size>end-payload or tag in tags:raise MetallibError('Truncated or duplicate tag')
   tags[tag]=data[payload:payload+size];tag_position=payload+size
  if not ended:raise MetallibError('Missing entry terminator')
  for tag,size in [(b'TYPE',1),(b'HASH',32),(b'MDSZ',8),(b'OFFT',24)]:
   if len(tags.get(tag,b''))!=size:raise MetallibError('Missing or unsupported tag '+repr(tag))
  name=tags.get(b'NAME',b'')
  if not 2<=len(name)<=256 or name[-1]!=0 or b'\0' in name[:-1]:raise MetallibError('Malformed function name')
  try:name=name[:-1].decode('utf-8')
  except UnicodeDecodeError:raise MetallibError('Non UTF-8 function name')
  if name in names:raise MetallibError('Duplicate function name')
  names.add(name);size=struct.unpack('<Q',tags[b'MDSZ'])[0];rel=struct.unpack_from('<Q',tags[b'OFFT'],16)[0]
  if not 20<=size<=16*1024*1024 or rel>bc_length or size>bc_length-rel:raise MetallibError('Invalid module range')
  wrapped=data[bc+rel:bc+rel+size]
  if sha(wrapped)!=tags[b'HASH'].hex():raise MetallibError('Module HASH differs')
  if wrapped[:4]!=bytes.fromhex('dec0170b'):raise MetallibError('AIR wrapper required; native-only library is not a semantic input')
  version,body_offset,body_length,cpu=struct.unpack_from('<4I',wrapped,4)
  if version!=0 or body_offset<20 or body_offset>len(wrapped) or body_length>len(wrapped)-body_offset or wrapped[body_offset:body_offset+4]!=b'BC\xc0\xde':raise MetallibError('Invalid bitcode wrapper')
  modules.append({'name':name,'type':tags[b'TYPE'][0],'offset':bc+rel,'bytes':size,'sha256':sha(wrapped),
                  'bitcode_bytes':body_length,'wrapper_CPU_type':cpu,'wrapped_AIR':wrapped})
  position=end
 if position!=limit+4 or data[position:position+4]!=b'ENDT':raise MetallibError('Function list extent/terminator differs from observed format')
 return modules
def extract(data,function):
 matches=[m for m in indexed_modules(data) if m['name']==function]
 if len(matches)!=1:raise MetallibError('Named function absent or ambiguous')
 if matches[0]['type']!=2:raise MetallibError('Compute kernel required')
 return matches[0]
