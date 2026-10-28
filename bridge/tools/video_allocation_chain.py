#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Hash-bound offline video allocation chain; never calls IOKit or GPU methods."""
import argparse, hashlib, json, struct
from pathlib import Path
from compare_video_profile import file_bytes, symbols_and_external_relocations

IO_SHA='37e563d6cf3626101f30b1727a4f60dec02152dff9c74c0269c30c213a7320c8'
GE_SHA='44f131a958d48afd6ab675a851330c37506557c9d499484170c886c3731bdbb3'
BUNDLES=[('kernel','5b7f7b9ae30112a9e4c8c8165425b54efa430e2887b648fc7ce28a0ad2cfacd1'),('nvidia','4762e35ab7362b70d28bfd308dcb589aae5fd83e00a8a570dc75ae204ef2ee09'),('backing','d7d30a96d89e38919b430c1dfeabef082882f3c701b4f8c60e368c210a77f064')]
REGIONS=[('io',0x9f70,2532,'1846ead1bc333cb0249a67da9a727e7c76e0e1558e62103dfe5b0b9c08f6c59b'),('io',0xa99c,342,'db704005579c2f1e52b109b4489f6f3da1df8a5f378fa8dd877a5d3158004627'),('io',0x23542,220,'ced8e5ef6733aa28fe4a18adb16611563f35f826ba2dfc2bee19c052eaba37ae'),('io',0x3eb08,85,'350a18df48790510ed7c5a6f2bfa6b6a89a2bddfad5ec1513853dd30db699a58'),('io',0x2361e,415,'9f2d9cf4bc74bf52a0b94ea3fdf55874245e7db48a09bbb6f17d48094de336a0'),('ge',0xdd82,37,'1cac0020e7d550925d94816d926035bb03c8a32c6fd275297d615dc0726115cf'),('ge',0x5c442,10,'aafd66af2c321a1032ffdbaea51ef446e7df7cd4b20fe53e4fdf6af362acadb2'),('ge',0x5c44c,151,'a6f1d1451743da03f3b46d7dc5d0b07fb5f5e1b8186cfcce2798fc9489aa3487'),('ge',0x5c700,429,'1e6edc726c479cbad5242372fb3421853c51808f60e92085d48382068d10fb69'),('ge',0x5d808,1574,'a48d0736fb85415067b97e26ec66f96f7e5d50ae8d59bbd3f8d2ec5947ad0d4d')]
EVIDENCE=[('kernel','ev_73185ac90e6c691e4d2eca5f95e61e33d6f341b329cd17b6934db77cab79f6b9',0x9f70,2532,IO_SHA),('kernel','ev_01ac18b1c4508e4d43852ca05e5a96648ca38b1837066e3b58b4940a4dc4ba05',0xa99c,342,IO_SHA),('kernel','ev_667eb7ed391641392816e6530d629a25b4bf4ac542f5d2b7a85607be5379554c',0x23542,220,IO_SHA),('kernel','ev_24d9dc5d00456c0b012472ddcff41be371ec547b05a0e15ee16ae5203eba11b7',0x3eb08,85,IO_SHA),('nvidia','ev_6d564b892aef2099950162711b0a0439915776eece5f14da918f47f9999d3b03',0xdd82,37,GE_SHA),('nvidia','ev_57331f0571fdeb06049f79fbb093da3d997443930f63f5b79cc6d765da842aa0',0x5c700,429,GE_SHA),('nvidia','ev_2b6896b8c75304325670b863f96ad65078fcbb86a545a57b3ad5bf95fdf7243a',0x5d808,1574,GE_SHA),('backing','ev_3e853af7b343a8582dfa04f1efd51c872776b26b75364b367770cb54ab453303',0x2361e,415,IO_SHA)]

def sha(b):return hashlib.sha256(b).hexdigest()
def need(x,reason):
 if not x:raise ValueError(reason)
def at(buf,address,n):return file_bytes(buf,address,n)[1]
def direct(buf,address,target):
 b=at(buf,address,5);need(b[0]==0xe8 and address+5+struct.unpack('<i',b[1:])[0]==target,'direct call '+hex(address))
def slot(buf,rel,symbols,base,offset,expected):
 address=base+offset;v=struct.unpack('<Q',at(buf,address,8))[0];entries=rel.get(address,[])
 if isinstance(expected,tuple):
  target,name=expected
  need(v==target and not entries,'vtable word '+hex(address))
  need(any(s['value']==v and s['name']==name and s['type']&0x0e==0x0e for s in symbols),'vtable target symbol '+hex(address))
 else:need(v==0 and len(entries)==1 and entries[0]['symbol']['name']==expected,'vtable relocation '+hex(address))

def audit(io,ge,bundles):
 need(sha(io)==IO_SHA and sha(ge)==GE_SHA,'installed binary identity')
 for name,expected in BUNDLES:need(sha(bundles[name])==expected,'evidence bundle '+name)
 docs={k:json.loads(v) for k,v in bundles.items()}
 for bundle,eid,address,length,target in EVIDENCE:
  found=[r for r in docs[bundle]['records'] if r.get('evidence_id')==eid];need(len(found)==1,'evidence '+eid)
  r=found[0];p=r['normalized_result']['procedure'];body=p['body']
  need(r['subject']['digest']['sha256']==target and p['address']==hex(address) and body['available'] and body['contains_entry'] and not body['non_contiguous'] and body['total_bytes']==length,'evidence scope '+eid)
 for target,address,length,expected in REGIONS:need(sha(at(io if target=='io' else ge,address,length))==expected,'code region '+hex(address))
 for address,raw in [(0x9fa1,'443b8fdc060000'),(0xa3b1,'ff90700a0000'),(0xaa01,'ff9040010000'),(0xaa2b,'ff9028010000'),(0x23563,'ba0a000000'),(0x23568,'ff90d0080000'),(0x3eb1f,'ff90700a0000'),(0x3eb3c,'ff9038010000'),(0x2363d,'f680780c000002'),(0x2364c,'ff90d8010000'),(0x23669,'41ff91c0080000'),(0x236f3,'f683f400000001')]:need(at(io,address,len(bytes.fromhex(raw)))==bytes.fromhex(raw),'IO instruction '+hex(address))
 for address,raw in [(0xdd88,'bf00040000'),(0x5c469,'488d05903c0300'),(0x5c470,'488903')]:need(at(ge,address,len(bytes.fromhex(raw)))==bytes.fromhex(raw),'NVIDIA instruction '+hex(address))
 for source,target in [(0xa9ea,0x23542),(0xaadb,0x21a10),(0x2368e,0x237be),(0x236e2,0x545c2)]:direct(io,source,target)
 for source,target in [(0xdd8d,0x5c42e),(0xdd98,0x5c442)]:direct(ge,source,target)
 gs,gr=symbols_and_external_relocations(ge);_,ir=symbols_and_external_relocations(io)
 for base,off,target in [(0x90ff8,0xa68,'__ZN15IOAccelContext213getDataBufferEP29IOAccelContextGetDataBufferInP30IOAccelContextGetDataBufferOutP22IOAccelResourcePrivatey'),(0x90ff8,0xa70,'__ZN15IOAccelContext218allocOneDataBufferEbj'),(0x7cba0,0x8d0,'__ZN22IOGraphicsAccelerator214createResourceEP14IOAccelShared2j'),(0x7cba0,0xa70,(0xdd82,'__ZN13nvAccelerator11newResourceEv')),(0x7cba0,0x8c0,(0xe068,'__ZN13nvAccelerator15createVidMemoryEP14IOAccelShared2P16IOAccelResource2yPv')),(0x90100,0x128,'__ZN16IOAccelResource221allocDataBufferMemoryEP14IOAccelShared2bj'),(0x90100,0x138,(0x5c700,'__ZN15nvTextureBuffer4initEP22IOGraphicsAccelerator2P14IOAccelShared2j')),(0x90100,0x140,(0x5d808,'__ZN15nvTextureBuffer10initializeEP22IOAccelNewResourceArgsy'))]:slot(ge,gr,gs,base,off,target)
 need(len(ir.get(0x23721,[]))==1 and ir[0x23721][0]['symbol']['name']=='__ZN18IOMemoryDescriptor19createMappingInTaskEP4taskyjyy','mapping relocation')
 return {'status':'STATIC_PASS','IOAcceleratorFamily2_SHA256':IO_SHA,'GeForce_SHA256':GE_SHA,'evidence_ids':[r[1] for r in EVIDENCE],'regions_checked':len(REGIONS),'nvidia_vtable_slots_checked':8,'native_calls':0,'GPU_commands':0,'hardware_video_execution_proved':False,'limits':['On-disk paths and vtables are static observations; live dispatch and branch choices are not observed.','The 0x400 allocation is a kernel-object allocation size, not a video frame or VRAM size.','Backing, mappings, cleanup and private input values remain unqualified on a real video request.','No authorization to call or construct private requests follows from this analysis.']}
def main():
 p=argparse.ArgumentParser(description=__doc__)
 for n in ('io','ge','kernel','nvidia','backing','out'):p.add_argument('--'+n,type=Path,required=True)
 a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required');buf={k:getattr(a,k).read_bytes() for k,_ in BUNDLES};io=a.io.read_bytes();ge=a.ge.read_bytes();r=audit(io,ge,buf)
 # Verify that tampering with both binary inputs and each private bundle fails closed.
 rejected=[]
 for name in ('io','ge','kernel','nvidia','backing'):
  altered=bytearray(io if name=='io' else ge if name=='ge' else buf[name]);altered[len(altered)//2]^=1
  b=dict(buf);bad_io=io;bad_ge=ge
  if name=='io':bad_io=bytes(altered)
  elif name=='ge':bad_ge=bytes(altered)
  else:b[name]=bytes(altered)
  try:audit(bad_io,bad_ge,b)
  except ValueError:rejected.append(name)
  else:raise ValueError('tamper not rejected '+name)
 r['tamper_controls_rejected']=rejected
 with a.out.open('x') as f:json.dump(r,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(r))
if __name__=='__main__':main()
