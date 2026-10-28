// SPDX-License-Identifier: MIT
#pragma once
#include <cstddef>
#include <cstdint>

// Written by the x86_64 tail before it jumps to the real function. Only r14,
// argument 0 (size) and the matched caller are recorded; the other slots are
// reserved and remain zero. The tail does not call C, dereference arguments,
// alter FP/vector state or replace a return value. Consume only after drain.
struct alignas(128) KPAllocRecord {
    uint64_t r14, args[6], reserved, caller, flags, rax, r10, r11, ready, padding[2];
};
static_assert(sizeof(KPAllocRecord)==128 && offsetof(KPAllocRecord,ready)==104, "assembly layout");
constexpr unsigned KPAllocCapacity=64;
extern "C" {
extern uint64_t KPAllocActive, KPAllocExpected, KPAllocCount, KPAllocDropped, KPAllocInflight;
extern KPAllocRecord KPAllocRecords[KPAllocCapacity];
extern void *KPAllocOriginal;
void KPAllocTail();
uint64_t KPInvokeNative(uint64_t selector,uint64_t flags);
uint64_t KPInvokeMatch(uint64_t selector,uint64_t flags);
uint64_t KPInvokeMiss(uint64_t selector,uint64_t flags);
extern const char KPInvokeMatchReturn;
void *KPInvokeAllocator(uint64_t selector,const void *nothrowArgument);
extern const char KPInvokeAllocatorReturn;
}
