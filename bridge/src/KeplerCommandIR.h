// Portable command-state ABI for the experimental AIR frontend/runtime.
// This is not Apple's native ICB layout and carries approved catalogue tokens.
#pragma once
#include <stdint.h>
#define KP_COMMAND_CONTEXT_MAGIC 0x4b504343u
#define KP_COMMAND_RECORD_MAGIC 0x4b504952u
#define KP_COMMAND_PIPELINE_MAGIC 0x4b504950u
#define KP_COMMAND_IR_VERSION 1u
#define KP_COMMAND_RECORD_BYTES 128u
#define KP_COMMAND_MAX_RECORDS 8u
#define KP_COMMAND_MAX_BINDINGS 3u
#define KP_COMMAND_IR_VERSION2 2u
#define KP_COMMAND_STABLE_CONTEXT_MAGIC 0x4b505343u
#define KP_COMMAND_STABLE_CONTEXT_VERSION 3u
#define KP_COMMAND_STABLE_PIPELINE_MAGIC 0x4b505350u
#define KP_COMMAND_V2_MAX_BINDINGS 4u
#define KP_COMMAND_FLAG_BUFFER3 256u
#define KP_COMMAND_MAX_PIPELINES 8u
#define KP_COMMAND_FLAG_PIPELINE 1u
#define KP_COMMAND_FLAG_DISPATCH 2u
#define KP_COMMAND_FLAG_SHARED 4u
#define KP_COMMAND_FLAG_BARRIER 8u
#define KP_COMMAND_FLAG_BUFFER0 16u
#define KP_COMMAND_FLAG_ERROR 0x80000000u
#define KP_COMMAND_FLAG_STAGE_IN 128u
struct KPCommandContext {
    uint32_t magic,version,capacity,max_bindings;
    uint64_t records_address;
    uint32_t record_bytes,pipeline_count;
};
// Native source producers only. The reflected root still points to the32-byte
// base; the host owns this complete extension. Records remain ABI v2, and the
// unchanged materializer never receives an unresolved stable identity.
struct KPCommandPipelineIdentity {
    uint64_t identity,parameters_address;
    uint32_t groups[3],local[3],shared_bytes,constant_index,reserved[2];
};
struct KPStableCommandContext {
    struct KPCommandContext base;
    struct KPCommandPipelineIdentity pipelines[KP_COMMAND_MAX_PIPELINES];
};
struct KPCommandRecord {
    uint32_t magic,flags;
    uint64_t pipeline_token;
    uint32_t groups[3],dispatch_kind; // 0 threadgroups; 1 grid threads
    uint32_t local[3],reserved1;
    uint64_t buffers[3];
    uint32_t shared_bytes,error;
    uint32_t stage_origin[3],stage_size[3],reserved[6];
};
// v2 preserves v1 offsets and uses two formerly reserved words for buffer3.
// Runtime and producer must agree on version2 in the context before writing.
struct KPCommandRecordV2 {
    uint32_t magic,flags;
    uint64_t pipeline_token;
    uint32_t groups[3],dispatch_kind;
    uint32_t local[3],reserved1;
    uint64_t buffers012[3];
    uint32_t shared_bytes,error;
    uint32_t stage_origin[3],stage_size[3];
    uint64_t buffer3;
    uint32_t reserved[4];
};
#ifdef __cplusplus
static_assert(sizeof(KPCommandContext)==32&&sizeof(KPCommandRecord)==128,"Command IR ABI");
static_assert(sizeof(KPCommandRecordV2)==128,"Command IR v2 ABI");
static_assert(sizeof(KPCommandPipelineIdentity)==56&&sizeof(KPStableCommandContext)==480,"Stable context ABI");
#endif
