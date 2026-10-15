#!/usr/bin/env python3
"""Read the observed version-7 NVIDIA shader container; never send it to GPU."""
from pathlib import Path
import struct
import json
import hashlib
import argparse

parser=argparse.ArgumentParser()
parser.add_argument('input',type=Path)
parser.add_argument('--json',type=Path)
parser.add_argument('--code',type=Path)
args=parser.parse_args()
data=args.input.read_bytes()
assert len(data)>=32
version,total=struct.unpack_from('<II',data)
assert version in (7,8) and total==len(data)
offset=8;visited=set();sections=[];native=[]
while True:
    assert offset not in visited and 0<=offset<=len(data)-16
    visited.add(offset)
    following,kind,size=struct.unpack_from('<QII',data,offset)
    start=offset+16;end=start+size
    assert end<=len(data)
    payload=data[start:end]
    section={'header_offset':offset,'type':hex(kind),'payload_offset':start,'payload_bytes':size,
             'following_relative_offset':following,'sha256':hashlib.sha256(payload).hexdigest()}
    if kind==1:
        assert size==4;section['stage_value']=struct.unpack('<I',payload)[0]
    if kind==0x10004:
        section['metadata_u32']=list(struct.unpack('<'+'I'*(size//4),payload[:size//4*4]))
    if kind==0x10005:
        native.append(payload);section['meaning']='native shader code; verified separately with envydis'
    sections.append(section)
    if following==0:break
    assert following>=16+size
    offset+=following
assert len(native)==1
if args.code:args.code.write_bytes(native[0])
result={'input':str(args.input),'container_version':version,'file_bytes':len(data),
        'sections':sections,'native_code_bytes':len(native[0]),
        'native_code_sha256':hashlib.sha256(native[0]).hexdigest(),
        'scope':'observed shader container only; opaque metadata is not assumed to be understood'}
if args.json:args.json.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
