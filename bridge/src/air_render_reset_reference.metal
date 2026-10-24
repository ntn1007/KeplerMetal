// SPDX-License-Identifier: MIT
#include <metal_stdlib>
using namespace metal;
struct Context { uint magic,version,capacity,recordBytes;ulong records,reserved; };
kernel void probe_boundary(device ulong *root [[buffer(0)]],uint gid [[thread_position_in_grid]]) {
    if(!root[0])return;
    device Context *c=reinterpret_cast<device Context*>(root[0]);
    if(c->magic!=0x4b505243u||c->version!=1||!c->capacity||c->capacity>16||
       c->recordBytes!=64||c->reserved||gid>=c->capacity||!c->records||
       c->records>1099511626752ul||(c->records&15ul))return;
    device uint4 *record=reinterpret_cast<device uint4*>(c->records+ulong(gid)*64ul);
    for(uint i=0;i<4;i++)record[i]=uint4(0);
}
