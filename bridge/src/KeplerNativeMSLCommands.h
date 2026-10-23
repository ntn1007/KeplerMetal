// SPDX-License-Identifier: MIT
// Opt-in source lowering for the existing Kepler CommandIR v2 ABI.
// The builder supplies this file as a local <metal_command_buffer> header.
// No SDK file is replaced. This is not Apple's ICB representation or resource ID.
// One writer per record; copy sources must already be complete. Host-owned
// context/record allocation and resource lifetimes are mandatory preconditions.
#pragma once
#include <metal_stdlib>
#include "KeplerCommandIR.h"

static_assert(__builtin_offsetof(KPCommandContext,records_address)==16 &&
              __builtin_offsetof(KPCommandRecordV2,pipeline_token)==8 &&
              __builtin_offsetof(KPCommandRecordV2,groups)==16 &&
              __builtin_offsetof(KPCommandRecordV2,local)==32 &&
              __builtin_offsetof(KPCommandRecordV2,buffers012)==48 &&
              __builtin_offsetof(KPCommandRecordV2,shared_bytes)==72 &&
              __builtin_offsetof(KPCommandRecordV2,stage_origin)==80 &&
              __builtin_offsetof(KPCommandRecordV2,buffer3)==104,"Native MSL CommandIR offsets");

namespace metal { namespace kp_native_commands {
using command_buffer = device KPCommandContext*;
using compute_pipeline_state = ulong;

class compute_command {
    command_buffer context;
    uint index;

    device KPCommandRecordV2* record() const thread {
        if(!context || context->magic!=KP_COMMAND_CONTEXT_MAGIC ||
           context->version!=KP_COMMAND_IR_VERSION2 || context->capacity>KP_COMMAND_MAX_RECORDS ||
           index>=context->capacity || context->record_bytes!=KP_COMMAND_RECORD_BYTES)return nullptr;
        ulong base=context->records_address,span=ulong(context->capacity)*KP_COMMAND_RECORD_BYTES;
        // SM30 laboratory address domain. These checks do not replace the
        // host's allocation/ownership validation or validate arbitrary code.
        if(!base || (base&7ul) || base>=(1ul<<40) || span>(1ul<<40)-base)return nullptr;
        return reinterpret_cast<device KPCommandRecordV2*>(base)+index;
    }
    static void fail(device KPCommandRecordV2*r,uint code) {
        r->error=code;r->flags|=KP_COMMAND_FLAG_ERROR;
    }
    device KPCommandRecordV2* ready() const thread {
        device KPCommandRecordV2*r=record();
        if(r && r->magic!=KP_COMMAND_RECORD_MAGIC){fail(r,4);return nullptr;}
        return r;
    }
    void binding(ulong address,uint slot) const thread {
        device KPCommandRecordV2*r=ready();if(!r)return;
        if(slot>=KP_COMMAND_V2_MAX_BINDINGS || slot>=context->max_bindings){fail(r,2);return;}
        if(slot==3){r->buffer3=address;r->flags|=KP_COMMAND_FLAG_BUFFER3;}
        else{r->buffers012[slot]=address;r->flags|=KP_COMMAND_FLAG_BUFFER0<<slot;}
    }
public:
    explicit compute_command(command_buffer c,uint i) thread:context(c),index(i){}
    void reset() const thread {
        device KPCommandRecordV2*r=record();if(!r)return;
        device uint*words=reinterpret_cast<device uint*>(r);
        for(uint i=0;i<KP_COMMAND_RECORD_BYTES/4;i++)words[i]=0;
        r->magic=KP_COMMAND_RECORD_MAGIC;
    }
    void copy_command(const thread compute_command&source) const thread {
        device KPCommandRecordV2*r=record();if(!r)return;
        if(source.context!=context || source.index>=context->capacity){fail(r,5);return;}
        device KPCommandRecordV2*s=source.record();
        if(!s || s->magic!=KP_COMMAND_RECORD_MAGIC){fail(r,5);return;}
        device uint*dst=reinterpret_cast<device uint*>(r);
        device const uint*src=reinterpret_cast<device const uint*>(s);
        for(uint i=0;i<KP_COMMAND_RECORD_BYTES/4;i++)dst[i]=src[i];
    }
    void set_compute_pipeline_state(compute_pipeline_state token) const thread {
        device KPCommandRecordV2*r=ready();if(!r)return;
        if(uint(token>>32)!=KP_COMMAND_PIPELINE_MAGIC || context->pipeline_count>KP_COMMAND_MAX_PIPELINES ||
           uint(token)>=context->pipeline_count){fail(r,1);return;}
        r->pipeline_token=token;r->flags|=KP_COMMAND_FLAG_PIPELINE;
    }
    template<typename T>void set_kernel_buffer(device T*pointer,uint slot) const thread {
        binding(reinterpret_cast<ulong>(pointer),slot);
    }
    // Registered immutable buffer members are lowered to device const before
    // compilation. Reject remaining constant-space bindings: their numerical
    // pointer representation is not our 64-bit GPU-address wire contract.
    template<typename T>void set_kernel_buffer(constant T*,uint) const thread = delete;
    template<typename T>void set_kernel_buffer(device T*,size_t,uint) const thread = delete;
    template<typename T>void set_kernel_buffer(constant T*,size_t,uint) const thread = delete;
    void concurrent_dispatch_threadgroups(uint3 groups,uint3 local) const thread {
        device KPCommandRecordV2*r=ready();if(!r)return;
        for(uint i=0;i<3;i++){r->groups[i]=groups[i];r->local[i]=local[i];}
        r->dispatch_kind=0;r->flags|=KP_COMMAND_FLAG_DISPATCH;
    }
    void concurrent_dispatch_threads(uint3 threads,uint3 local) const thread {
        concurrent_dispatch_threadgroups(threads,local);
        device KPCommandRecordV2*r=ready();if(r)r->dispatch_kind=1;
    }
    void set_threadgroup_memory_length(uint bytes,uint slot) const thread {
        device KPCommandRecordV2*r=ready();if(!r)return;
        if(slot){fail(r,3);return;}r->shared_bytes=bytes;r->flags|=KP_COMMAND_FLAG_SHARED;
    }
    void set_barrier() const thread {device KPCommandRecordV2*r=ready();if(r)r->flags|=KP_COMMAND_FLAG_BARRIER;}
    void clear_barrier() const thread {device KPCommandRecordV2*r=ready();if(r)r->flags&=~KP_COMMAND_FLAG_BARRIER;}
    void set_stage_in_region(uint3 origin,uint3 size) const thread {
        device KPCommandRecordV2*r=ready();if(!r)return;
        for(uint i=0;i<3;i++){r->stage_origin[i]=origin[i];r->stage_size[i]=size[i];}
        r->flags|=KP_COMMAND_FLAG_STAGE_IN;
    }
};
}} // namespace metal::kp_native_commands

// metal_stdlib already declares Apple's opaque types. Keep those definitions
// intact and lower subsequent source tokens to this explicitly selected ABI.
// Qualified metal:: names and ordinary 'using namespace metal' both work.
#define command_buffer kp_native_commands::command_buffer
#define compute_pipeline_state kp_native_commands::compute_pipeline_state
#define compute_command kp_native_commands::compute_command
