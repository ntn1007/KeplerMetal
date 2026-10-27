// SPDX-License-Identifier: MIT
#pragma once
#include <stdint.h>
#define KP_RENDER_VERTEX_EXTENSION_MAGIC 0x4b505658u
#define KP_RENDER_VERTEX_EXTENSION_VERSION 1u
#define KP_RENDER_VERTEX_BINDING_BYTES 32u
#define KP_RENDER_VERTEX_BINDING_LIMIT 64u
struct KPRenderVertexExtension {
 uint32_t magic,version,count,entryBytes;
 uint64_t table,reserved;
};
static_assert(sizeof(KPRenderVertexExtension)==32,"Vertex extension ABI");
