// SPDX-License-Identifier: MIT
#pragma once
#ifdef __METAL_VERSION__
typedef unsigned long KPRenderStateIdentity;
#else
#include <stdint.h>
typedef uint64_t KPRenderStateIdentity;
#endif
// Catalogue identities are process-local project tokens, never native PSO IDs.
#define KP_RENDER_STATE_COMMAND_MAGIC 0x4b505353u
#define KP_RENDER_STATE_COMMAND_BYTES 64u
#define KP_RENDER_STATE_ID_TAG 0x4b50535200000000ul
struct KPRenderStateCommandRecord {
    unsigned int magic,kind,arguments[5],reserved0;
    KPRenderStateIdentity state_identity;
    unsigned int reserved[6];
};
struct KPRenderStateTemplate {
    unsigned int arguments[5],kind,occupied,reserved0;
    KPRenderStateIdentity state_identity;
    unsigned int logical_slot,reserved[5];
};
static_assert(sizeof(KPRenderStateCommandRecord)==64&&sizeof(KPRenderStateTemplate)==64,"Render state ABI");
