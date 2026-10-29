// SPDX-License-Identifier: MIT
#include <cstdio>
#include <cstdlib>
#include <cstring>
struct Device { unsigned long registry; };
extern "C" { Device KMDevice={0}; int KMMap=0; int KMOutputWrong=0; int KMItemWrong=0; int KMFilterAccept=1; int KMCachePresent=0; int KMCacheHit=0; int KMAbsentPresent=0; int KMAbsentHit=0; int KMServicePresent=1; void* KMKeyForSet=nullptr; void* KMValueForSet=nullptr; }
static int fake=0;
static int count=0;
static bool null_result=false;
static bool compare_equal=false;
static bool available=true;
static bool simulate_other=false;
static void* stored_key=nullptr;
static void* stored_value=nullptr;
extern "C" { extern const char KMIGPU[]="IGPU"; }
static const char KMName[]="GFX0";
extern "C" __attribute__((noinline,used)) void KMTraceReady(unsigned long marker,unsigned long registry) { __asm__ volatile("" : : "r"(marker),"r"(registry) : "memory"); }
extern "C" __attribute__((noinline)) unsigned long KMGetRegistry(Device* p) { p->registry=0x12345;return 0; }
extern "C" __attribute__((noinline)) void* KMGetList() { return &count; }
extern "C" __attribute__((noinline)) unsigned long KMGetBatch(void* p) { return p==&count ? (unsigned long)count : 99; }
extern "C" __attribute__((noinline)) void* KMGetDict(void* p) { return null_result ? nullptr : p; }
extern "C" __attribute__((noinline)) void* KMGetReg(void* p) { return p ? &KMDevice.registry : nullptr; }
extern "C" __attribute__((noinline)) const char* KMGetName(void* p) { return p ? KMName : nullptr; }
extern "C" __attribute__((noinline)) int KMCompare(const char* p,const char* key) { return p==KMName && key==KMIGPU && compare_equal; }
extern "C" __attribute__((noinline)) unsigned long KMNextBatch(void) { return 0; }
extern "C" __attribute__((noinline)) void KMSet(void*,void* key,void* value) { stored_key=key;stored_value=value; }
extern "C" __attribute__((noinline)) void KMApplyFunction(void*,void(*callback)(void*,void*,void*),void* context) { callback(stored_key,stored_value,context); if(simulate_other) { bool old=available;available=true;callback(&fake,&fake,&fake);available=old; } }
extern "C" __attribute__((noinline)) void KMGetAvailable(void*,unsigned char* output) { *output=available?1:0; }
extern "C" __attribute__((noinline)) void KMAppend(void*,void*) { __asm__ volatile("" ::: "memory"); }
extern "C" __attribute__((noinline)) unsigned long KMArrayCount(void*) { return 1; }
extern "C" __attribute__((noinline)) void* KMArrayItem(void*,unsigned long) { return KMItemWrong ? (void*)&fake : (void*)&KMDevice; }
extern "C" { extern const char KMFirstKey[]="PresentIORegKeysAndValues"; extern const char KMAbsentKey[]="AbsentIORegKeys"; extern const char KMServiceKey[]="Service"; }
extern "C" __attribute__((noinline)) void* KMFirst(void*,const void*) { return KMCachePresent ? (void*)&fake : nullptr; }
extern "C" __attribute__((noinline)) void* KMSecond(void*,const void*) { return KMCacheHit ? (void*)&fake : nullptr; }
extern "C" __attribute__((noinline)) void* KMAbsent(void*,const void*) { return KMAbsentPresent ? (void*)&fake : nullptr; }
extern "C" __attribute__((noinline)) int KMContains(void*) { return KMAbsentHit; }
extern "C" __attribute__((noinline)) int KMService(void*,const void*) { return KMServicePresent; }
extern "C" __attribute__((noinline)) void* KMProperty(void*) { return KMFilterAccept ? (void*)&fake : nullptr; }
extern "C" unsigned long KMRun(void);
int main(int argc,char**argv) { count=argc>1?std::atoi(argv[1]):1;null_result=argc>2&&!std::strcmp(argv[2],"null");compare_equal=argc>2&&!std::strcmp(argv[2],"equal");available=!(argc>2&&(!std::strcmp(argv[2],"unavailable")||!std::strcmp(argv[2],"unavailableother")));simulate_other=argc>2&&(!std::strcmp(argv[2],"other")||!std::strcmp(argv[2],"unavailableother"));KMOutputWrong=argc>2&&!std::strcmp(argv[2],"wrongout");KMItemWrong=argc>2&&!std::strcmp(argv[2],"wrongitem");KMFilterAccept=!(argc>2&&!std::strcmp(argv[2],"rejectfilter"));KMCachePresent=argc>2&&(!std::strcmp(argv[2],"cachehit")||!std::strcmp(argv[2],"cachemiss"));KMCacheHit=argc>2&&!std::strcmp(argv[2],"cachehit");KMAbsentPresent=argc>2&&!std::strcmp(argv[2],"absenthit");KMAbsentHit=KMAbsentPresent;KMServicePresent=!(argc>2&&!std::strcmp(argv[2],"noservice"));bool wrong=argc>2&&!std::strcmp(argv[2],"wrong");bool wrongid=argc>2&&!std::strcmp(argv[2],"wrongid");KMKeyForSet=argc>2&&!std::strcmp(argv[2],"wrongkey")?(void*)&fake:(void*)&KMDevice.registry;KMValueForSet=argc>2&&!std::strcmp(argv[2],"wrongvalue")?(void*)&fake:(void*)&KMDevice;KMTraceReady(wrong?0xabc1:0xabc0,wrongid?0x99999:0x12345);unsigned long result=KMRun();std::printf("cpu_batch=%lu\n",result);return result==(unsigned long)count?0:1; }
