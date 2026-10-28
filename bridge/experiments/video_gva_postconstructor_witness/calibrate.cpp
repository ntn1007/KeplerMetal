// SPDX-License-Identifier: MIT
// CPU-only synthetic ABI controls. No Metal, IOKit, framework hooks or vendor code.
#include "witness.h"
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <new>

extern "C" {
uint64_t KPAllocActive=0, KPAllocExpected=0, KPAllocCount=0, KPAllocDropped=0, KPAllocInflight=0;
KPAllocRecord KPAllocRecords[KPAllocCapacity]{};
void *KPAllocOriginal=nullptr;
uint64_t KPMockR14=0,KPMockArgs[6]{},KPMockStackArg=0,KPMockFlags=0,KPMockRax=0,KPMockR10=0,KPMockR11=0;
void KPMockOriginal();
}

static void need(bool ok,const char *why){if(!ok){std::fprintf(stderr,"FAIL: %s\n",why);std::exit(1);}}
struct Mock { uint64_t r14,args[6],stack,flags,rax,r10,r11,result;int err; };
static Mock call(uint64_t (*function)(uint64_t,uint64_t),uint64_t selector,uint64_t flags){
    errno=EDOM;uint64_t result=function(selector,flags);int saved=errno;
    Mock m{};m.r14=KPMockR14;std::memcpy(m.args,KPMockArgs,sizeof(m.args));m.stack=KPMockStackArg;
    m.flags=KPMockFlags;m.rax=KPMockRax;m.r10=KPMockR10;m.r11=KPMockR11;m.result=result;m.err=saved;return m;
}
static void compare(const Mock &a,const Mock &b){
    constexpr uint64_t mask=0x8d5;
    need(a.r14==b.r14 && !std::memcmp(a.args,b.args,sizeof(a.args)) && a.stack==b.stack &&
         (a.flags&mask)==(b.flags&mask) && a.rax==b.rax && a.r10==b.r10 && a.r11==b.r11 &&
         a.result==b.result && a.err==b.err,"forwarded machine state differs");
}
static uint64_t flagsFor(unsigned n){
    const uint64_t bits[]={1,4,16,64,128,2048};uint64_t result=2;
    for(unsigned i=0;i<6;i++)if(n&(1u<<i))result|=bits[i];return result;
}
static void reset(){KPAllocActive=0;KPAllocExpected=(uintptr_t)&KPInvokeMatchReturn;KPAllocCount=KPAllocDropped=KPAllocInflight=0;std::memset(KPAllocRecords,0,sizeof(KPAllocRecords));}

int main(){
    KPAllocOriginal=(void*)&KPMockOriginal;unsigned cases=0;
    const uint64_t selectors[]={0,2,9,0xffffffff};
    for(uint64_t selector:selectors)for(unsigned i=0;i<64;i++){
        reset();auto native=call(KPInvokeNative,selector,flagsFor(i));KPAllocActive=1;
        auto actual=call(KPInvokeMatch,selector,flagsFor(i));KPAllocActive=0;compare(native,actual);
        auto &r=KPAllocRecords[0];need(KPAllocCount==1 && !KPAllocDropped && !KPAllocInflight && r.ready==1 &&
            r.r14==selector && r.args[0]==native.args[0] && r.args[1]==0 && r.reserved==0 &&
            r.caller==(uintptr_t)&KPInvokeMatchReturn && r.flags==0 && r.rax==0 && r.r10==0 && r.r11==0,
            "matching record differs");cases++;
    }
    reset();KPAllocActive=1;auto expected=call(KPInvokeNative,9,flagsFor(63));auto missed=call(KPInvokeMiss,9,flagsFor(63));
    compare(expected,missed);need(KPAllocCount==0 && KPAllocInflight==0,"nonmatching caller recorded");
    KPAllocActive=0;auto disabled=call(KPInvokeMatch,2,flagsFor(0));auto disabledNative=call(KPInvokeNative,2,flagsFor(0));
    compare(disabledNative,disabled);need(KPAllocCount==0,"disabled call recorded");
    reset();KPAllocActive=1;
    for(unsigned i=0;i<80;i++){auto r=call(KPInvokeMatch,i,flagsFor(i%64));need(r.r14==i,"saturation forwarded selector differs");}
    KPAllocActive=0;need(KPAllocCount==80 && KPAllocDropped==16 && KPAllocInflight==0,"saturation accounting differs");
    for(unsigned i=0;i<64;i++)need(KPAllocRecords[i].ready==1 && KPAllocRecords[i].r14==i,"saturation record differs");
    reset();
    using Allocator=void*(*)(std::size_t,const std::nothrow_t&) noexcept;
    Allocator alloc=static_cast<Allocator>(::operator new);
    KPAllocOriginal=reinterpret_cast<void*>(alloc);KPAllocExpected=(uintptr_t)&KPInvokeAllocatorReturn;KPAllocActive=1;
    void *p=KPInvokeAllocator(9,&std::nothrow);KPAllocActive=0;
    need(p && KPAllocCount==1 && KPAllocRecords[0].r14==9 && KPAllocRecords[0].args[0]==0x600 &&
         KPAllocRecords[0].args[1]==0 && KPAllocRecords[0].ready==1 && !KPAllocInflight,
         "public nothrow allocation differs");
    std::memset(p,0x5a,0x600);for(unsigned i=0;i<0x600;i++)need(static_cast<unsigned char*>(p)[i]==0x5a,"allocation memory differs");
    ::operator delete(p);
    std::printf("{\"status\":\"PASS\",\"scalar_flag_cases\":%u,\"mismatched_caller_refused\":true,\"disabled_not_recorded\":true,\"saturation_calls\":80,\"saturation_drops\":16,\"real_nothrow_allocation_bytes\":1536,\"GPU_execution\":false,\"vendor_execution\":false}\n",cases);
}
