// SPDX-License-Identifier: MIT
// Bounded geometry only; this does not authorize a GPU command or shader.
#pragma once
#include <algorithm>
#include <cstdint>
#include <vector>
namespace KPPartialPlan {
struct Size { uint32_t x,y,z; };
struct Region { Size origin,groups,actual; };
struct AxisPart { uint32_t origin,count,actual; };
inline bool validRange(uint64_t address,uint64_t size) { return address && size && address<=UINT64_MAX-size; }
inline bool disjoint(uint64_t a,uint64_t as,uint64_t b,uint64_t bs) {
 return validRange(a,as)&&validRange(b,bs)&&(a+as<=b||b+bs<=a);
}
inline bool plan(Size grid,Size nominal,std::vector<Region>&out) {
 out.clear();const uint32_t g[3]={grid.x,grid.y,grid.z},l[3]={nominal.x,nominal.y,nominal.z};
 for(unsigned a=0;a<3;a++)if(!g[a]||!l[a]||g[a]>1023||l[a]>1023)return false;
 const uint64_t total=uint64_t(g[0])*g[1]*g[2],local=uint64_t(l[0])*l[1]*l[2];
 if(total>1024||local>128)return false;
 std::vector<AxisPart> axis[3];
 for(unsigned a=0;a<3;a++){
  uint32_t q=g[a]/l[a],r=g[a]%l[a];
  if(q)axis[a].push_back({0,q,l[a]});
  if(r)axis[a].push_back({q*l[a],1,r});
 }
 for(auto x:axis[0])for(auto y:axis[1])for(auto z:axis[2]){
  uint32_t capacity=128/(x.actual*y.actual*z.actual);
  for(uint32_t xs=0;xs<x.count;){uint32_t xc=std::min(x.count-xs,capacity);
   for(uint32_t ys=0;ys<y.count;){uint32_t yc=std::min(y.count-ys,capacity/xc);
    for(uint32_t zs=0;zs<z.count;){uint32_t zc=std::min(z.count-zs,capacity/(xc*yc));
     if(out.size()>=16){out.clear();return false;}
     out.push_back({{x.origin+xs*x.actual,y.origin+ys*y.actual,z.origin+zs*z.actual},{xc,yc,zc},{x.actual,y.actual,z.actual}});zs+=zc;
    }ys+=yc;
   }xs+=xc;
  }
 }
 return !out.empty();
}
}
