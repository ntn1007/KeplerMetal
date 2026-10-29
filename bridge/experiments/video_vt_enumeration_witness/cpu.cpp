// SPDX-License-Identifier: MIT
#include <cstdio>
#include <cstdlib>
static int value=0;
extern "C" __attribute__((noinline,used)) void KMTraceReady(unsigned long x) { __asm__ volatile("" : : "r"(x) : "memory"); }
extern "C" __attribute__((noinline)) void* KMGetList() { return &value; }
extern "C" __attribute__((noinline)) unsigned long KMGetBatch(void* p) { return p==&value ? (unsigned long)value : 99; }
extern "C" unsigned long KMRun(void);
int main(int argc,char** argv) { value=argc>1?std::atoi(argv[1]):1; KMTraceReady(argc>2?0xabc1:0xabc0); unsigned long result=KMRun(); std::printf("cpu_batch=%lu\n",result); return result==(unsigned long)value?0:1; }
