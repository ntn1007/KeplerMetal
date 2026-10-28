// SPDX-License-Identifier: MIT
#include "GuardedAliasBackend.h"
#include <atomic>
#include <cassert>
#include <mutex>
#include <thread>
#include <vector>
using namespace kepler_video;
struct Mock {
 uint32_t refs=1; Handle context=33,shared=44; int open3=0,open6=0,assoc=0,close=0,release=0,refFailAt=0,changeAt=0,equalsFailAt=0;
 unsigned callsRefs=0,callsEqual=0,opens3=0,opens6=0,assocs=0,closes=0,releases=0;
 bool outputOnError=false;
};
int opOpen(void *u,Handle,uint32_t type,Handle*out){auto&m=*static_cast<Mock*>(u);if(type==3){m.opens3++;*out=(!m.open3||m.outputOnError)?m.context:0;return m.open3;}m.opens6++;*out=(!m.open6||m.outputOnError)?m.shared:0;if(!m.open6&&m.shared==44)++m.refs;return m.open6;}
int opRefs(void*u,Handle,uint32_t*out){auto&m=*static_cast<Mock*>(u);++m.callsRefs;if((int)m.callsRefs==m.changeAt)++m.refs;*out=m.refs;return (int)m.callsRefs==m.refFailAt?17:0;}
bool opEqual(void*u,Handle a,Handle b){auto&m=*static_cast<Mock*>(u);++m.callsEqual;return (int)m.callsEqual!=m.equalsFailAt&&a==b;}
int opAssociate(void*u,Handle,Handle){auto&m=*static_cast<Mock*>(u);++m.assocs;return m.assoc;}
int opClose(void*u,Handle){auto&m=*static_cast<Mock*>(u);++m.closes;return m.close;}
int opRelease(void*u,Handle){auto&m=*static_cast<Mock*>(u);++m.releases;if(!m.release)--m.refs;return m.release;}
GuardOps ops(Mock&m){return {&m,opOpen,opRefs,opEqual,opAssociate,opClose,opRelease};}
void nominal(){Mock m;GuardedAliasBackend g(ops(m),44);Lease l(g.backend());assert(l.start(42,true));assert(l.close());assert(l.close());assert(m.refs==1&&m.opens3==1&&m.opens6==1&&m.assocs==1&&m.closes==1&&m.releases==1);assert(g.report().qualified&&!g.report().rejected&&!g.report().unreleased&&!g.report().postcondition_failed);}
void failures(){
 {Mock m;GuardedAliasBackend g(ops(m),0);Lease l(g.backend());assert(!l.start(42,true));assert(m.opens3==0&&g.report().rejected);}
 {Mock m;m.open3=9;m.outputOnError=true;GuardedAliasBackend g(ops(m),44);Lease l(g.backend());assert(!l.start(42,true));assert(g.report().ambiguous_output&&m.closes==0);}
 {Mock m;m.context=44;GuardedAliasBackend g(ops(m),44);Lease l(g.backend());assert(!l.start(42,true));assert(g.report().unreleased&&m.closes==0&&m.opens6==0);}
 {Mock m;m.refFailAt=1;GuardedAliasBackend g(ops(m),44);Lease l(g.backend());assert(!l.start(42,true));assert(g.report().rejected&&m.opens6==0&&m.closes==1&&m.releases==0);}
 {Mock m;m.open6=9;m.outputOnError=true;GuardedAliasBackend g(ops(m),44);Lease l(g.backend());assert(!l.start(42,true));assert(g.report().ambiguous_output&&m.closes==1&&m.releases==0);}
 {Mock m;m.shared=45;GuardedAliasBackend g(ops(m),44);Lease l(g.backend());assert(!l.start(42,true));assert(g.report().unreleased&&m.assocs==0&&m.closes==1&&m.releases==0);}
 for(int i=1;i<=3;i++){Mock m;m.equalsFailAt=i;GuardedAliasBackend g(ops(m),44);Lease l(g.backend());assert(!l.start(42,true));assert(g.report().unreleased&&m.assocs==0&&m.closes==1&&m.releases==0);}
 {Mock m;m.refFailAt=2;GuardedAliasBackend g(ops(m),44);Lease l(g.backend());assert(!l.start(42,true));assert(g.report().unreleased&&m.assocs==0&&m.releases==0);}
 {Mock m;m.assoc=9;GuardedAliasBackend g(ops(m),44);Lease l(g.backend());assert(!l.start(42,true));assert(m.assocs==1&&m.closes==1&&m.releases==1&&m.refs==1);}
 {Mock m;m.close=9;GuardedAliasBackend g(ops(m),44);Lease l(g.backend());assert(l.start(42,true));assert(!l.close());assert(g.report().unreleased&&m.closes==1&&m.releases==0);}
 {Mock m;m.changeAt=3;GuardedAliasBackend g(ops(m),44);Lease l(g.backend());assert(l.start(42,true));assert(!l.close());assert(g.report().unreleased&&m.releases==0);}
 {Mock m;m.refFailAt=3;GuardedAliasBackend g(ops(m),44);Lease l(g.backend());assert(l.start(42,true));assert(!l.close());assert(g.report().unreleased&&m.releases==0);}
 {Mock m;m.release=9;GuardedAliasBackend g(ops(m),44);Lease l(g.backend());assert(l.start(42,true));assert(!l.close());assert(!l.close());assert(g.report().unreleased&&m.releases==1);}
 {Mock m;m.refFailAt=4;GuardedAliasBackend g(ops(m),44);Lease l(g.backend());assert(l.start(42,true));assert(!l.close());assert(g.report().postcondition_failed&&m.releases==1);}
 {Mock m;m.changeAt=4;GuardedAliasBackend g(ops(m),44);Lease l(g.backend());assert(l.start(42,true));assert(!l.close());assert(g.report().postcondition_failed&&m.releases==1);}
}
void cooperative_threads(){
 Mock m;std::mutex mx;std::atomic<unsigned> completed{0};std::vector<std::thread> ts;
 for(int i=0;i<8;i++)ts.emplace_back([&]{for(int j=0;j<200;j++){std::lock_guard<std::mutex> lock(mx);GuardedAliasBackend g(ops(m),44);Lease l(g.backend());assert(l.start(42,true));assert(l.close());++completed;}});
 for(auto&t:ts)t.join();assert(completed==1600&&m.refs==1&&m.releases==1600&&m.assocs==1600);
}
int main(){nominal();failures();cooperative_threads();}
