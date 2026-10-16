// SPDX-License-Identifier: MIT
#pragma once
#define KPREG_CAPACITY 1024
#define KPREG_STRIDE_SHIFT 7
#ifndef __ASSEMBLER__
#include <cstdint>
#include <cstddef>
struct KPRegistryRecord {
    uint64_t index, arguments[6], caller, incomingRAX, flags, stack, incomingR10, incomingR11, ready, padding[2];
};
static_assert(sizeof(KPRegistryRecord)==128 && offsetof(KPRegistryRecord,arguments)==8
    && offsetof(KPRegistryRecord,caller)==56 && offsetof(KPRegistryRecord,incomingRAX)==64
    && offsetof(KPRegistryRecord,flags)==72 && offsetof(KPRegistryRecord,stack)==80
    && offsetof(KPRegistryRecord,incomingR10)==88 && offsetof(KPRegistryRecord,incomingR11)==96
    && offsetof(KPRegistryRecord,ready)==104,"Assembly record layout");
#endif
