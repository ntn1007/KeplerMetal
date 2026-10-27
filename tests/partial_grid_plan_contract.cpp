// SPDX-License-Identifier: MIT
#include "KeplerPartialGridPlan.h"
#include <cassert>
#include <set>
#include <tuple>
using KPPartialPlan::Size;
int main(){
 std::vector<KPPartialPlan::Region> regions;unsigned cases=0;
 for(unsigned gx=1;gx<=8;gx++)for(unsigned gy=1;gy<=6;gy++)for(unsigned gz=1;gz<=4;gz++)
  for(unsigned lx=1;lx<=5;lx++)for(unsigned ly=1;ly<=4;ly++)for(unsigned lz=1;lz<=3;lz++){
   Size g{gx,gy,gz},l{lx,ly,lz};bool ok=KPPartialPlan::plan(g,l,regions);if(!ok)continue;
   assert(regions.size()<=16);std::set<std::tuple<unsigned,unsigned,unsigned>> seen;
   for(const auto&r:regions){assert(r.actual.x&&r.actual.y&&r.actual.z);assert(uint64_t(r.actual.x)*r.actual.y*r.actual.z*r.groups.x*r.groups.y*r.groups.z<=128);
    for(unsigned z=0;z<r.groups.z;z++)for(unsigned y=0;y<r.groups.y;y++)for(unsigned x=0;x<r.groups.x;x++)
     for(unsigned tz=0;tz<r.actual.z;tz++)for(unsigned ty=0;ty<r.actual.y;ty++)for(unsigned tx=0;tx<r.actual.x;tx++){
      unsigned px=r.origin.x+x*r.actual.x+tx,py=r.origin.y+y*r.actual.y+ty,pz=r.origin.z+z*r.actual.z+tz;
      assert(px<gx&&py<gy&&pz<gz);assert(seen.emplace(px,py,pz).second);
      unsigned bx=px/lx,by=py/ly,bz=pz/lz;
      assert(r.actual.x==std::min(lx,gx-bx*lx)&&r.actual.y==std::min(ly,gy-by*ly)&&r.actual.z==std::min(lz,gz-bz*lz));
      assert((r.origin.x/lx+x)==bx&&(r.origin.y/ly+y)==by&&(r.origin.z/lz+z)==bz);
     }
   }
   assert(seen.size()==gx*gy*gz);cases++;
  }
 assert(cases==11520);
 assert(KPPartialPlan::disjoint(100,10,110,5));assert(KPPartialPlan::disjoint(110,5,100,10));
 assert(!KPPartialPlan::disjoint(100,11,110,5));assert(!KPPartialPlan::disjoint(100,20,105,2));
 assert(!KPPartialPlan::disjoint(0,1,10,1));assert(!KPPartialPlan::disjoint(UINT64_MAX-2,4,10,1));
 assert(!KPPartialPlan::plan({0,1,1},{1,1,1},regions));assert(!KPPartialPlan::plan({1024,1,1},{2,1,1},regions));
 assert(!KPPartialPlan::plan({1023,2,1},{2,1,1},regions));assert(!KPPartialPlan::plan({3,1,1},{129,1,1},regions));
 assert(KPPartialPlan::plan({1023,1,1},{4,1,1},regions));assert(regions.size()==9);
 assert(KPPartialPlan::plan({14,23,3},{12,3,2},regions));assert(regions.size()==16);
 assert(!KPPartialPlan::plan({3,21,15},{2,5,7},regions));assert(regions.empty());
}
