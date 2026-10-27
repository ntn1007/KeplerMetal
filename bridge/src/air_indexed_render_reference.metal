// SPDX-License-Identifier: MIT
#include <metal_stdlib>
#include "KeplerIndexedRenderRecords.h"
using namespace metal;
struct Context {uint magic,version,capacity,recordBytes;ulong records,reserved;};
inline device uint *record_at(ulong address,uint slot){
 if(!address)return nullptr;
 device const Context *c=reinterpret_cast<device const Context*>(address);
 if(c->magic!=0x4b505243u||c->version!=1||!c->capacity||c->capacity>16||c->recordBytes!=64||
    c->reserved||slot>=c->capacity||!c->records||c->records>1099511626752ul||(c->records&15ul))return nullptr;
 return reinterpret_cast<device uint*>(c->records+ulong(slot)*64ul);
}
inline void reset_at(ulong address,uint slot){device uint*r=record_at(address,slot);if(r)for(uint i=0;i<16;i++)r[i]=0;}
inline void indexed_at(ulong address,uint slot,ulong pointer,uint kind,uint count,uint instances,uint vertexBase,uint base){
 device uint *r=record_at(address,slot);if(!r)return;
 ulong identity=ulong(r[8])|(ulong(r[9])<<32);
 device const KPRenderIndexExtension *extension=reinterpret_cast<device const KPRenderIndexExtension*>(address+32ul);
 bool found=false;uint first=0;
 if(extension->magic==KP_RENDER_INDEX_EXTENSION_MAGIC&&extension->version==1&&extension->count&&extension->count<=16&&
    extension->entryBytes==48&&!extension->reserved&&extension->table==address+64ul){
  device const KPRenderIndexBinding *table=reinterpret_cast<device const KPRenderIndexBinding*>(extension->table);
  for(uint i=0;i<extension->count;i++){
   KPRenderIndexBinding b=table[i];ulong element=kind==1?2ul:4ul;
   if(!b.stateIdentity||(identity&&identity!=b.stateIdentity)||slot!=b.logicalSlot||kind!=b.kind||b.reserved||b.padding||
      !b.baseAddress||b.baseAddress>=1099511627776ul||b.byteLength>1099511627776ul-b.baseAddress||
      b.byteLength!=ulong(b.maximumCount)*element||(b.baseAddress&(element-1ul))||
      pointer<b.baseAddress||pointer-b.baseAddress>b.byteLength||((pointer-b.baseAddress)&(element-1ul)))continue;
   first=uint(kind==1?((pointer-b.baseAddress)>>1):((pointer-b.baseAddress)>>2));found=true;break;
  }
 }
 for(uint i=0;i<16;i++)r[i]=0;
 if(found){r[0]=0x4b505353u;r[1]=kind;r[2]=count;r[3]=instances;r[4]=first;r[5]=vertexBase;r[6]=base;r[8]=uint(identity);r[9]=uint(identity>>32);}
}
kernel void probe_boundary(device const ulong *root [[buffer(0)]],device uint *out [[buffer(1)]],
 device const uint *indices [[buffer(2)]],constant uint4 &config [[buffer(3)]],
 device ushort *index16 [[buffer(4)]],device uint *index32 [[buffer(5)]],uint gid [[thread_position_in_grid]]){
 if(gid>=config.x)return;
 uint slot=indices[gid],x=(gid*1664525u+config.y)^slot;
 if(config.w==2u)reset_at(root[0],slot);
 if((x&config.z)==0u){
  uint first=3u*((x>>3u)&1u),count=3u*((x>>4u)&3u),instances=(x>>6u)&1u;
  if((gid&1u)==0u)indexed_at(root[0],slot,reinterpret_cast<ulong>(index16+first),1,count,instances,2u,1u);
  else indexed_at(root[0],slot,reinterpret_cast<ulong>(index32+first),2,count,instances,uint(-2),2u);
  x^=0xa511e9b3u;
 }else{reset_at(root[0],slot);x+=0x7f4a7c15u;}
 if(config.w==3u){
  uint first=3u-3u*((((gid*1664525u+config.y)^slot)>>3u)&1u);
  if((gid&1u)==0u)indexed_at(root[0],slot,reinterpret_cast<ulong>(index16+first),1,3u,1u,2u,1u);
  else indexed_at(root[0],slot,reinterpret_cast<ulong>(index32+first),2,3u,1u,uint(-2),2u);
 }
 if(config.w==1u)reset_at(root[0],slot);
 uint shift=(gid&15u)+1u;
 out[gid]=((x<<shift)|(x>>(32u-shift)))^(slot*0x9e3779b9u);
}
