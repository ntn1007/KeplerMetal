// SPDX-License-Identifier: MIT
#include <cstdio>
#include <cstdlib>
#include <cstring>
struct Device { unsigned long registry; };
extern "C" { Device KMDevice={0}; }
static int count=0;
static bool null_result=false;
extern "C" __attribute__((noinline,used)) void KMTraceReady(unsigned long marker,unsigned long registry) { __asm__ volatile("" : : "r"(marker),"r"(registry) : "memory"); }
extern "C" __attribute__((noinline)) unsigned long KMGetRegistry(Device* p) { p->registry=0x12345;return 0; }
extern "C" __attribute__((noinline)) void* KMGetList() { return &count; }
extern "C" __attribute__((noinline)) unsigned long KMGetBatch(void* p) { return p==&count ? (unsigned long)count : 99; }
extern "C" __attribute__((noinline)) void* KMFilter(void* p) { return null_result ? nullptr : p; }
extern "C" unsigned long KMRun(void);
int main(int argc,char**argv) { count=argc>1?std::atoi(argv[1]):1;null_result=argc>2&&!std::strcmp(argv[2],"null");bool wrong=argc>2&&!std::strcmp(argv[2],"wrong");bool wrongid=argc>2&&!std::strcmp(argv[2],"wrongid");KMTraceReady(wrong?0xabc1:0xabc0,wrongid?0x99999:0x12345);unsigned long result=KMRun();std::printf("cpu_batch=%lu\n",result);return result==(unsigned long)count?0:1; }
