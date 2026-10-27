// SPDX-License-Identifier: MIT
#pragma once
#ifdef __METAL_VERSION__
typedef unsigned long KPIndexU64;
#else
#include <stdint.h>
typedef uint64_t KPIndexU64;
#endif
#define KP_RENDER_INDEX_EXTENSION_MAGIC 0x4b504958u
#define KP_RENDER_INDEX_EXTENSION_VERSION 1u
#define KP_RENDER_INDEX_BINDING_BYTES 48u
#define KP_RENDER_INDEX_BINDING_LIMIT 16u
// Appended after the unchanged 32-byte render-root header. The binding table
// is owned by the same allocation, immediately following this extension.
struct KPRenderIndexExtension {
    unsigned int magic,version,count,entryBytes;
    KPIndexU64 table,reserved;
};
struct KPRenderIndexBinding {
    KPIndexU64 stateIdentity,baseAddress,byteLength;
    unsigned int logicalSlot,kind,maximumCount,reserved;
    KPIndexU64 padding;
};
static_assert(sizeof(KPRenderIndexExtension)==32,"Index extension ABI");
static_assert(sizeof(KPRenderIndexBinding)==48,"Index binding ABI");
