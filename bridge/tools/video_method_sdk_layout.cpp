// SPDX-License-Identifier: MIT
// Compile-time check of the SDK kernel ABI; never linked or executed.
#include <IOKit/IOUserClient.h>
#include <stddef.h>
static_assert(sizeof(IOByteCount)==8, "kernel IOByteCount must be 64-bit");
static_assert(sizeof(IOMethod)==16, "x86_64 member function pointer size");
static_assert(sizeof(IOExternalMethod)==48, "kernel descriptor size");
static_assert(offsetof(IOExternalMethod,object)==0, "object offset");
static_assert(offsetof(IOExternalMethod,func)==8, "member pointer offset");
static_assert(offsetof(IOExternalMethod,flags)==24, "flags offset");
static_assert(offsetof(IOExternalMethod,count0)==32, "count0 offset");
static_assert(offsetof(IOExternalMethod,count1)==40, "count1 offset");
static_assert(kIOUCScalarIScalarO==0 && kIOUCStructIStructO==3 && kIOUCScalarIStructI==4, "method types");
static_assert(kIOUCForegroundOnly==16 && kIOUCVariableStructureSize==0xffffffff, "flags");
