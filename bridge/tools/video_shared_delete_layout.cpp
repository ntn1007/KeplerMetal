// SPDX-License-Identifier: MIT
// Kernel SDK x86_64 field offsets and method shape; compiled only, never executed.
#include <IOKit/IOUserClient.h>
#include <stddef.h>
static_assert(sizeof(IOByteCount)==8, "kernel counts must be 64-bit");
static_assert(sizeof(IOExternalMethod)==48, "legacy method descriptor layout");
static_assert(offsetof(IOExternalMethodArguments,scalarInput)==0x20, "scalar input pointer offset");
static_assert(offsetof(IOExternalMethodArguments,scalarInputCount)==0x28, "scalar input count offset");
static_assert(kIOUCScalarIScalarO==0, "legacy scalar method type");
