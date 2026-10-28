// SPDX-License-Identifier: MIT
// Own CPU process; tests dyld interposition across a separate synthetic image.
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <dlfcn.h>
#include <new>
#include <unistd.h>

extern "C" void *KPSyntheticMatch(uint64_t,const void*);
extern "C" void *KPSyntheticMiss(uint64_t,const void*);
extern "C" const char KPSyntheticMatchReturn;
using Arm=bool(*)(uintptr_t);
using Stop=bool(*)(uint64_t*,uint64_t*,uint64_t*,uint64_t*);
static void need(bool b,const char*s){if(!b){std::fprintf(stderr,"FAIL %s\n",s);std::exit(1);}}
int main(){
    alarm(15);auto arm=reinterpret_cast<Arm>(dlsym(RTLD_DEFAULT,"KPAllocCalibrationArm"));
    auto stop=reinterpret_cast<Stop>(dlsym(RTLD_DEFAULT,"KPAllocCalibrationStop"));need(arm&&stop,"observer unavailable");
    need(arm((uintptr_t)&KPSyntheticMatchReturn),"cannot arm");
    void *miss=KPSyntheticMiss(2,&std::nothrow);void *match=KPSyntheticMatch(9,&std::nothrow);
    uint64_t count=0,dropped=0,selector=0,size=0;need(stop(&count,&dropped,&selector,&size),"cannot drain");
    need(miss&&match&&count==1&&!dropped&&selector==9&&size==0x600,"interposed event or allocation differs");
    static_cast<unsigned char*>(match)[0]=0x6a;static_cast<unsigned char*>(match)[0x5ff]=0xa6;
    need(static_cast<unsigned char*>(match)[0]==0x6a&&static_cast<unsigned char*>(match)[0x5ff]==0xa6,"allocation inaccessible");
    ::operator delete(match);::operator delete(miss);alarm(0);
    std::printf("{\"status\":\"PASS\",\"cross_image_interposition\":true,\"matching_calls\":1,\"other_call_excluded\":true,\"selector\":9,\"allocation_bytes\":1536,\"GPU_execution\":false,\"vendor_execution\":false}\n");
}
