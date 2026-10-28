#!/usr/bin/env python3
"""Unpack an Apple pbzx payload to a new local cpio; never executes its contents."""
import argparse, hashlib, json, lzma, struct
from pathlib import Path

def exact(f,n):
 v=f.read(n)
 if len(v)!=n:raise ValueError('truncated pbzx')
 return v

def unpack(source,dest):
 digest=hashlib.sha256();total=chunks=0
 with source.open('rb') as f, dest.open('xb') as out:
  if exact(f,4)!=b'pbzx':raise ValueError('not pbzx')
  flags=struct.unpack('>Q',exact(f,8))[0]
  while flags & 0x1000000:
   flags,length=struct.unpack('>QQ',exact(f,16));chunks+=1
   if length==0 or length>67108864:raise ValueError('invalid chunk size')
   data=exact(f,length)
   block=lzma.decompress(data,format=lzma.FORMAT_XZ,memlimit=268435456) if data.startswith(b'\xfd7zXZ\x00') else data
   if len(block)>33554432:raise ValueError('decompressed chunk too large')
   out.write(block);digest.update(block);total+=len(block)
  if f.read(1):raise ValueError('trailing bytes')
  if not chunks:raise ValueError('empty payload')
 return {'status':'PASS','chunks':chunks,'cpio_bytes':total,'cpio_SHA256':digest.hexdigest(),'source':str(source),'output':str(dest),'executed':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('source',type=Path);p.add_argument('output',type=Path);a=p.parse_args();print(json.dumps(unpack(a.source,a.output),sort_keys=True))
