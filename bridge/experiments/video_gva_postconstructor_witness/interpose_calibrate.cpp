// SPDX-License-Identifier: MIT
// Own CPU process; tests dyld interposition across a separate synthetic image.
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <dlfcn.h>
#include <new>
#include <unistd.h>

extern "C" void KPSyntheticMatch(uint64_t,void*);
extern "C" void KPSyntheticMiss(uint64_t,void*);
extern "C" const char KPSyntheticMatchReturn;
using Arm=bool(*)(uintptr_t);
using Stop=bool(*)(uint64_t*,uint64_t*,uint64_t*,uint64_t*);
static void need(bool b,const char*s){if(!b){std::fprintf(stderr,"FAIL %s\n",s);std::exit(1);}}
int main(){
    alarm(15);auto arm=reinterpret_cast<Arm>(dlsym(RTLD_DEFAULT,"KPAllocCalibrationArm"));
    auto stop=reinterpret_cast<Stop>(dlsym(RTLD_DEFAULT,"KPAllocCalibrationStop"));need(arm&&stop,"observer unavailable");
    void *miss=::operator new(16);void *match=::operator new(16);
    uintptr_t expected=(uintptr_t)match;
    need(arm((uintptr_t)&KPSyntheticMatchReturn),"cannot arm");
    KPSyntheticMiss(2,miss);KPSyntheticMatch(9,match);
    uint64_t count=0,dropped=0,selector=0,size=0;need(stop(&count,&dropped,&selector,&size),"cannot drain");
    need(count==1&&!dropped&&selector==9&&size==expected,"interposed event or argument differs");
    alarm(0);
    std::printf("{\"status\":\"PASS\",\"cross_image_interposition\":true,\"matching_calls\":1,\"other_call_excluded\":true,\"selector\":9,\"calls_returned\":true,\"deallocation_independently_proved\":false,\"GPU_execution\":false,\"vendor_execution\":false}\n");
}
