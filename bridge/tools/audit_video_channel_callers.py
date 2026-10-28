#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit static call *and* jump sites for pinned GeForce channel functions.

Does not execute provider, kext, selector or GPU work. A lack of direct
references is not evidence that a function cannot be reached indirectly.
"""
import argparse,bisect,hashlib,json,re,struct,subprocess
from pathlib import Path
from compare_video_profile import file_bytes,symbols_and_external_relocations

PINS={
 'sierra':{'sha':'25a0bccd7caa884d6aa964743b35f879ec326c46d255dc6212c47e7a20f6f38e','acquire':0x136fe,'video':0x1382c,'refs':[(0x10129,'call',0x136fe),(0x13831,'jmp',0x136fe),(0x2d41d,'call',0x136fe),(0x4b51c,'call',0x136fe),(0x5ec35,'call',0x136fe)]},
 'high':{'sha':'bcd3d0f6d90235b1fa6e0d96904bbee829063de1b60a01362946dc8aad9a1791','acquire':0x14a4a,'video':0x14de0,'refs':[(0x14de5,'jmp',0x14a4a),(0x54bf2,'call',0x14a4a)]},
 'current':{'sha':'44f131a958d48afd6ab675a851330c37506557c9d499484170c886c3731bdbb3','acquire':0x148a6,'video':0x14c56,'refs':[(0x14c5b,'jmp',0x148a6),(0x55ba5,'call',0x148a6)]},
}
def need(x,msg):
 if not x:raise ValueError(msg)
def parse_direct(text,targets):
 rows=[]
 for line in text.splitlines():
  m=re.match(r'^\s*([0-9a-f]+):\s+(?:(?:[0-9a-f]{2})\s+)+(callq?|jmpq?)\s+0x([0-9a-f]+)\b',line)
  if m and int(m.group(3),16) in targets:rows.append((int(m.group(1),16),'call' if m.group(2).startswith('call') else 'jmp',int(m.group(3),16)))
 return rows
def verify_direct(actual,expected):
 need(actual==expected,'direct-call/jump inventory changed')
def validate_site(data,site,kind,target):
 off,raw=file_bytes(data,site,5);need(raw[0]==({'call':0xe8,'jmp':0xe9}[kind]),'not a direct rel32 branch');dest=site+5+struct.unpack_from('<i',raw,1)[0];need(dest==target,'branch target mismatch')
 return {'file_offset':hex(off),'instruction_SHA256':hashlib.sha256(raw).hexdigest()}
def process(label,path):
 pin=PINS[label];data=path.read_bytes();need(hashlib.sha256(data).hexdigest()==pin['sha'],'input hash changed '+label)
 syms,_=symbols_and_external_relocations(data)
 def unique(prefix,value):
  matches=[x for x in syms if x['name'].startswith(prefix) and x['value']==value and x['type']&0x0e==0x0e];need(len(matches)==1,'target symbol '+prefix);return matches[0]['name']
 acquire=unique('__ZN16nvChannelManager14AcquireChannel',pin['acquire']);video=unique('__ZN16nvChannelManager19AcquireVideoChannel',pin['video'])
 p=subprocess.run(['xcrun','llvm-objdump','-d',str(path)],capture_output=True,text=True,check=True,timeout=90)
 hits=parse_direct(p.stdout,{pin['acquire'],pin['video']});verify_direct(hits,pin['refs'])
 symbols=sorted((x['value'],x['name']) for x in syms if x['type']&0x0e==0x0e);values=[x[0] for x in symbols];rows=[]
 for addr,kind,target in hits:
  owner=bisect.bisect_right(values,addr)-1;need(owner>=0,'missing preceding symbol');entry=symbols[owner]
  rows.append({'site':hex(addr),'kind':kind,'target':hex(target),'nearest_preceding_defined_symbol':entry[1],'nearest_symbol_address':hex(entry[0]),**validate_site(data,addr,kind,target)})
 need(sum(x[1]=='jmp' and x[0]==pin['video']+5 for x in hits)==1,'video wrapper tail jump')
 return {'file_SHA256':pin['sha'],'acquire_symbol':acquire,'acquire_address':hex(pin['acquire']),'video_wrapper_symbol':video,'video_wrapper_address':hex(pin['video']),'direct_branches_to_wrapper':sum(x[2]==pin['video'] for x in hits),'direct_branches':rows}
def current_path(data,path):
 # These are exact-file observations, not a decoder ABI or live-path proof.
 ranges=[(0x148a6,0x14910,'f8dcf36cb27261e97e12fc8a8457091f25fd801fed02801505103a5307c95d46'),(0x39f82,0x3a13a,'e1aef31d412727a5ff226feb33a5f4d85ba4794617b3bbc4e17a6de7a03ac96f'),(0x3e90a,0x3ea05,'3fd71b9f2a2f88f1bb98f2785a6bed274560cf56bf6604ae7a7ad78b88d8f2c5'),(0x55a64,0x55bfe,'5bde88b6a1eea7fe7fe670f6654a199989207e0151266d17dae7ba368c58313c')]
 for start,end,h in ranges:
  _,raw=file_bytes(data,start,end-start);need(hashlib.sha256(raw).hexdigest()==h,'current function range changed')
 for base,expected in [(0x14910,[0x148dc,0x148e0,0x148e7,0x148c3,0x148c3,0x148c3]),(0x3a13c,[0x39fbf,0x39fea,0x3a08f,0x39fab,0x39fab,0x39fab,0x3a0e1])]:
  _,raw=file_bytes(data,base,4*len(expected));actual=[base+n for n in struct.unpack('<'+'i'*len(expected),raw)];need(actual==expected,'channel jump table changed')
 p=subprocess.run(['xcrun','llvm-objdump','-d',str(path)],capture_output=True,text=True,check=True,timeout=90);lines={}
 for line in p.stdout.splitlines():
  m=re.match(r'^\s*([0-9a-f]+):\s+(?:(?:[0-9a-f]{2})\s+)+(.+)$',line)
  if m:lines[int(m.group(1),16)]=re.sub(r'\s+',' ',m.group(2).split('##')[0].strip())
 patterns={0x148ce:r'testl \$0xe8e00, 0x808\(%rax\)',0x39fb5:r'callq 0x3e90a',0x3e91d:r'cmpl \$0x0, 0xff4\(%rax\)',0x3e924:r'je 0x3e9f8',0x3e9f8:r'movl %ebx, %eax',0x55aa2:r'movl \$0x1, %r13d',0x55ac5:r'movl \$0x2, %r13d',0x55b9f:r'movl %r13d, %edx',0x55ba5:r'callq 0x148a6'}
 for address,pat in patterns.items():need(address in lines and re.search(pat,lines[address]),'current path instruction '+hex(address))
 return {'conditional_channel_types_3_4_5':'manager and object jump tables route these to the same video branches','guard_mask':'0xe8e00','create_object_video_zero_class':'returns zero without reaching CreateObject','direct_submitter_type_assignments':[1,2],'inference_scope':'static pinned control-flow only; runtime flags, class and ABI unknown'}
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in PINS:p.add_argument('--'+n,type=Path,required=True)
 p.add_argument('--out',type=Path,required=True);a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required')
 out={'status':'STATIC_CHANNEL_BRANCH_INVENTORY_PASS','profiles':{n:process(n,getattr(a,n)) for n in PINS},'current_video_path':current_path(a.current.read_bytes(),a.current),'scope':'On-disk direct rel32 call/jump inventory only; no proof of live reachability, indirect dispatch, ABI compatibility, video channel allocation, or hardware decode.','executed_vendor_or_gpu_code':False}
 with a.out.open('x') as f:json.dump(out,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(out,sort_keys=True))
if __name__=='__main__':main()
