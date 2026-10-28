#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare pinned Nouveau video class selection with the on-disk Mac driver.

Read-only: no driver loading, private call, channel creation or GPU submission.
Matching class numbers do not establish a compatible command transport.
"""
import argparse,hashlib,json,re,struct,subprocess,tarfile
from pathlib import Path
from compare_video_profile import file_bytes,symbols_and_external_relocations

ARCHIVE='bce5f7fbebb934373b86c999a064d52fb5065878dc57f287f95346648ec832e9'
DRIVER='44f131a958d48afd6ab675a851330c37506557c9d499484170c886c3731bdbb3'
REA='401a07db63b466ad08f5dae49d9d4684fa50905167325508cae61dd1bc83c3dc'
MEMBERS={
 'src/gallium/drivers/nouveau/nvc0/nvc0_video.c':'2c1662f23fb1afe0fd76c758e4779eee0e0ede8562938f7479e45dd3bec118a6',
 'src/gallium/drivers/nouveau/nouveau_vp3_video.c':'d5cc2a6692f0db2a7218957c98d8ccf4e3792c70b8393d3e5cbc89ac46489a48',
 'src/nouveau/drm/nvif/class.h':'8486732ad1988054b5f2415970111bc19e4ebc8cf4b059288d462699e39e7a2a',
 'include/drm-uapi/nouveau_drm.h':'8cc1e1dbca4ddc4dd4df0c888ff493f4ef2b10648e7102540c6c755627a720dc',
}
FUNCTIONS={
 'properties':(0x9a90,0x9b79,'12cd1a4e2a2c3ccbb28bde37a9eb6c147fda24001eee12a7f9c15c7836c8c99e','__ZN13nvAccelerator18SetAccelPropertiesEv','ev_45f2e5ff493f8b1d4718c25d4676f71afd3786689af5819abc3860a1a09ebaa4'),
 'init_classes':(0x2cb9a,0x2ce65,'168f17bd024ef6abb80b172e434d3379d8c67b104e465276ecec984752429cbf','__ZN10nvFermiHAL11InitClassesEv','ev_5a5d5e4ee848324f75d166a41254d62f074f316bdb4bb820103e0aa3c7a0a27d'),
 'first_supported':(0x3e64c,0x3e694,'d30030b6ae5f8107cd522cce0fd6d73b3155c0d602296ea1a264dd8a02c1df0e','__ZN5nvHAL22GetFirstClassSupportedEPKjj','ev_54ad61326b3f4f16c9766cacc273c2aa387b2230c64eb825fa54f7f7158b4ccb'),
 'create_video':(0x3e90a,0x3ea05,'3fd71b9f2a2f88f1bb98f2785a6bed274560cf56bf6604ae7a7ad78b88d8f2c5','__ZN5nvHAL17CreateObjectVideoEP15nvGpFifoChannel','ev_d414fd7e6fa2d1d70d1524efc175674b096e77b932238ee79eb8e8280fa9bfda'),
}
# Independent byte checks against selected instructions; whole bodies are also pinned.
SITES={0x2ccba:'48b8b1950000b1900000',0x2ccdf:'8981f40f0000',0x2cce5:'48b8b2950000b2900000',0x2cd0a:'8981f80f0000',0x2cd10:'41c706b3900000',0x2cd2f:'8981fc0f0000',0x3e981:'8b80f80f0000',0x3e98d:'8b80fc0f0000',0x3e999:'8b80f40f0000',0x9ae5:'3db1950000',0x9aec:'3db1900000',0x9afa:'c745f003000000',0x9b1f:'b808000401'}
def need(v,m):
 if not v:raise ValueError(m)
def digest(data):return hashlib.sha256(data).hexdigest()
def hash_file(path):
 h=hashlib.sha256()
 with Path(path).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def check_fragments(s,fragments):
 for fragment in fragments:need(s.count(fragment)==1,'changed source anchor: '+fragment)
def verify_instructions(data):
 for addr,expected in SITES.items():
  _,raw=file_bytes(data,addr,len(bytes.fromhex(expected)));need(raw==bytes.fromhex(expected),'instruction '+hex(addr))
 _,table=file_bytes(data,0x3ea08,32);targets=[0x3ea08+x for x in struct.unpack('<8i',table)];need(targets==[0x3e97d,0x3e9f8,0x3e989,0x3e995,0x3e9f8,0x3e9f8,0x3e9f8,0x3e9a1],'channel jump table')
def inspect_sources(archive,tree):
 need(hash_file(archive)==ARCHIVE,'Mesa archive identity');found={};prefix='mesa-26.2.4/'
 with tarfile.open(archive,mode='r|xz') as tar:
  for entry in tar:
   if not entry.name.startswith(prefix):continue
   name=entry.name[len(prefix):]
   if name not in MEMBERS:continue
   need(name not in found and entry.isfile() and entry.size<1000000,'archive member');f=tar.extractfile(entry);need(f is not None,'missing archive data');raw=f.read();need(digest(raw)==MEMBERS[name] and (tree/name).read_bytes()==raw,'source mismatch '+name);found[name]=raw.decode('utf-8')
 need(set(found)==set(MEMBERS),'missing archive members')
 main=found['src/gallium/drivers/nouveau/nvc0/nvc0_video.c'];cap=found['src/gallium/drivers/nouveau/nouveau_vp3_video.c'];classes=found['src/nouveau/drm/nvif/class.h'];uapi=found['include/drm-uapi/nouveau_drm.h']
 check_fragments(main,['bool kepler = screen->device->chipset >= 0xe0;','nve0_args.engine = engine[i];','0x95b1, 0x95b1','0x95b2, 0x95b2','0x90b3, 0x90b3','if (screen->device->chipset < 0xd0) {','ret = nouveau_vp3_load_firmware(dec, templ->profile, screen->device->chipset);','nvc0_decoder_bsp_end(dec, desc, target, comm_seq, &vp_caps, &is_ref, refs);','nvc0_decoder_vp(dec, desc, target, comm_seq, vp_caps, is_ref, refs);','nvc0_decoder_ppp(dec, desc, target, comm_seq);'])
 need(re.search(r'unsigned engine\[\] = \{\s*NOUVEAU_FIFO_ENGINE_BSP,\s*NOUVEAU_FIFO_ENGINE_VP,\s*NOUVEAU_FIFO_ENGINE_PPP\s*\}',main),'engine order')
 need(re.search(r'for \(i = 0; i < 3; \+\+i\)\s*if \(i && !kepler\)',main),'channel branch')
 check_fragments(cap,['int vp5 = chipset >= 0xd0;','nouveau_object_mclass(channel, nouveau_decoder_msvld);','if (!vp5 && !(screen->firmware_info.profiles_checked & (1 << profile))) {','return vp5 || (screen->firmware_info.profiles_present & (1 << profile));'])
 for name,value in [('GK104_MSVLD',0x95b1),('GK104_MSPDEC',0x95b2),('GF100_MSPPP',0x90b3)]:
  m=re.search(r'^#define\s+'+name+r'\s+(0x[0-9a-fA-F]+)\s*$',classes,re.M);need(m and int(m.group(1),16)==value,'class '+name)
 for name,value in [('NOUVEAU_FIFO_ENGINE_BSP',8),('NOUVEAU_FIFO_ENGINE_VP',2),('NOUVEAU_FIFO_ENGINE_PPP',4)]:
  m=re.search(r'^#define\s+'+name+r'\s+(0x[0-9a-fA-F]+)\s*$',uapi,re.M);need(m and int(m.group(1),16)==value,'engine '+name)
 return {'archive_SHA256':ARCHIVE,'reference_version':'Mesa 26.2.4','recorded_upstream_reference':'96cb43121031992b85767f9c1be8f3f48e22b1d2','members_SHA256':MEMBERS,'archive_tree_matches':True,'kepler_engine_order':['BSP','VP','PPP'],'classes':['0x95b1','0x95b2','0x90b3'],'firmware_scope':'userspace file load applies only to chipset < 0xd0; kernel/firmware dependencies remain unproved'}
def inspect_binary(path,rea):
 data=path.read_bytes();need(digest(data)==DRIVER,'GeForce image changed');need(hash_file(rea)==REA,'REA bundle identity');bundle=json.loads(rea.read_text());records={r['evidence_id']:r for r in bundle['records']};syms,_=symbols_and_external_relocations(data);rows={}
 for name,(start,end,h,symbol,eid) in FUNCTIONS.items():
  matches=[s for s in syms if s['value']==start and s['name']==symbol];need(len(matches)==1,'symbol '+name)
  off,raw=file_bytes(data,start,end-start);need(digest(raw)==h,'function bytes '+name);r=records.get(eid);need(r and r['subject']['digest']['sha256']==DRIVER and r['parameters']['procedure']==hex(start) and r['operation']=='analyze_function','REA '+name)
  rows[name]={'address':hex(start),'file_offset':hex(off),'length':len(raw),'SHA256':h,'symbol':symbol,'REA_evidence_id':eid}
 verify_instructions(data)
 for addr,name in [(0x75eb4,b'IOVARendererID\0'),(0x75ec3,b'IOVARendererSubID\0')]:
  _,raw=file_bytes(data,addr,len(name));need(raw==name,'property name')
 return {'file_SHA256':DRIVER,'REA_bundle_SHA256':REA,'functions':rows,'class_candidates':{'0xff4':['0x95b1','0x90b1'],'0xff8':['0x95b2','0x90b2'],'0xffc':['0x90b3']},'conditional_channel_type_to_field':{'8':'0xff8','10':'0xffc','11':'0xff4'},'property_class_ambiguity':['0x95b1','0x90b1'],'dynamic_class_values_observed':False}
def parse_registry(text):
 ids=re.findall(r'<class nvAccelerator, id (0x[0-9a-f]+),',text);need(ids==['0x100000460'],'registry identity')
 def field(name):
  m=re.findall(r'"'+name+r'" = <([0-9a-fA-F]{8})>',text);need(len(m)==1,'registry field '+name);return int.from_bytes(bytes.fromhex(m[0]),'little')
 renderer,sub=field('IOVARendererID'),field('IOVARendererSubID');need(renderer==0x1040008 and sub==3,'registry values changed')
 return {'registry_id':int(ids[0],16),'renderer_id':renderer,'renderer_sub_id':sub,'registry_output_SHA256':digest(text.encode()),'matches_both_on_disk_class_branches':True,'runtime_branch_observed':False}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--archive',type=Path,required=True);p.add_argument('--tree',type=Path,required=True);p.add_argument('--driver',type=Path,required=True);p.add_argument('--rea',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'fresh output')
 src=inspect_sources(a.archive,a.tree);driver=inspect_binary(a.driver,a.rea);raw=subprocess.run(['ioreg','-r','-c','nvAccelerator','-w0'],capture_output=True,text=True,check=True,timeout=15).stdout;registry=parse_registry(raw)
 result={'status':'PASS_STATIC_CLASS_COMPARISON','nouveau':src,'macos':driver,'live_registry':registry,'scope':'Static source and on-disk analysis plus public registry observation. No proof of loaded instruction bytes, active class selection, channel creation, ABI compatibility, firmware state or video decode.','video_provider_or_private_selector_called':False,'GPU_dispatches':0,'system_modified':False}
 with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(result,sort_keys=True))
if __name__=='__main__':main()
