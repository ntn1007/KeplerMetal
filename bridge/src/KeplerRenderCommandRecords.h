// SPDX-License-Identifier: MIT
// Original scalar-only ABI. No Apple ICB identity, address or resource handle.
#pragma once
#define KP_RENDER_COMMAND_MAGIC 0x4b505244u
#define KP_RENDER_COMMAND_BYTES 32u
#define KP_RENDER_COMMAND_MAX_SLOTS 16u
struct KPRenderCommandRecord {
    unsigned int magic;
    unsigned int kind; // 0 direct, 1 UInt16 indexed, 2 UInt32 indexed
    unsigned int arguments[5]; // Native direct/indexed argument word order.
    unsigned int reserved;
};
static_assert(sizeof(KPRenderCommandRecord)==KP_RENDER_COMMAND_BYTES,"Render record ABI");
