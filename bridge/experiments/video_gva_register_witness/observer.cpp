// SPDX-License-Identifier: MIT
// CPU interposition calibration only. There is deliberately no AppleGVA hook.
#include "witness.h"
#include <cstdint>
#include <cstring>
#include <new>

using Allocator=void*(*)(std::size_t,const std::nothrow_t&) noexcept;
extern "C" {
#pragma GCC visibility push(hidden)
alignas(8) uint64_t KPAllocActive=0,KPAllocExpected=0,KPAllocCount=0,KPAllocDropped=0,KPAllocInflight=0;
alignas(128) KPAllocRecord KPAllocRecords[KPAllocCapacity]{};
void *KPAllocOriginal=reinterpret_cast<void*>(static_cast<Allocator>(::operator new));
#pragma GCC visibility pop
}
// The relocation refers to the real public operator; the observer itself
// does not call it through the interposed name. It is bound before constructors.
__attribute__((used,section("__DATA,__interpose"))) static const struct {
    const void *replacement,*original;
} pair={(const void*)&KPAllocTail,reinterpret_cast<const void*>(static_cast<Allocator>(::operator new))};

extern "C" bool KPAllocCalibrationArm(uintptr_t expected){
    if(!expected||!KPAllocOriginal||KPAllocOriginal==(void*)&KPAllocTail||
       __atomic_load_n(&KPAllocActive,__ATOMIC_ACQUIRE)||__atomic_load_n(&KPAllocInflight,__ATOMIC_ACQUIRE))return false;
    KPAllocExpected=expected;KPAllocCount=KPAllocDropped=0;std::memset(KPAllocRecords,0,sizeof(KPAllocRecords));
    __atomic_store_n(&KPAllocActive,1,__ATOMIC_RELEASE);return true;
}
extern "C" bool KPAllocCalibrationStop(uint64_t *count,uint64_t *dropped,uint64_t *value,uint64_t *size){
    __atomic_store_n(&KPAllocActive,0,__ATOMIC_RELEASE);
    if(__atomic_load_n(&KPAllocInflight,__ATOMIC_ACQUIRE)||!count||!dropped||!value||!size)return false;
    *count=KPAllocCount;*dropped=KPAllocDropped;
    if(*count==1 && KPAllocRecords[0].ready){*value=KPAllocRecords[0].r14;*size=KPAllocRecords[0].args[0];}else{*value=0;*size=0;}
    return true;
}
