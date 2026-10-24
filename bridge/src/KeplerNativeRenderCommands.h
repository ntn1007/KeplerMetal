// SPDX-License-Identifier: MIT
// Opt-in MSL source interface for the project's certified render-state ABI.
// Native Apple command-buffer/pipeline types and SDK files are not replaced.
#pragma once
#ifndef __METAL_VERSION__
#error This header is for Metal shader source
#endif
#include <metal_stdlib>
#include "KeplerRenderStateRecords.h"

namespace keplermetal {
// The host owns and validates the entire records allocation. Exactly one
// invocation may write a slot; copying requires a completed source writer.
// Tokens refer to a complete certified state at a logical slot, not a raw PSO.
struct render_command_buffer {
    device KPRenderStateCommandRecord *records;
    metal::uint capacity;
};
enum class index_type : metal::uint { uint16 = 1, uint32 = 2 };

class render_command {
    render_command_buffer buffer;
    metal::uint index;
    device KPRenderStateCommandRecord *record() const thread {
        if (!buffer.records || !buffer.capacity || buffer.capacity > 16u ||
            index >= buffer.capacity) return nullptr;
        return buffer.records + index;
    }
    bool draw(metal::uint kind, metal::uint first, metal::uint count,
              metal::uint instances, metal::int32_t baseVertex,
              metal::uint baseInstance) const thread {
        device KPRenderStateCommandRecord *r = record();
        if (!r) return false;
        KPRenderStateCommandRecord next = {};
        next.magic = KP_RENDER_STATE_COMMAND_MAGIC;
        next.kind = kind;
        next.arguments[0] = count;
        next.arguments[1] = instances;
        next.arguments[2] = first;
        next.arguments[3] = metal::uint(baseVertex);
        next.arguments[4] = baseInstance;
        next.state_identity = r->state_identity;
        *r = next;
        return true;
    }
public:
    explicit render_command(render_command_buffer b, metal::uint i) thread
        : buffer(b), index(i) {}
    bool reset() const thread {
        device KPRenderStateCommandRecord *r = record();
        if (!r) return false;
        KPRenderStateCommandRecord empty = {};
        *r = empty;
        return true;
    }
    bool set_render_state(KPRenderStateIdentity identity) const thread {
        device KPRenderStateCommandRecord *r = record();
        if (!r) return false;
        r->state_identity = identity;
        return true;
    }
    // Only triangles in the host-certified envelope are currently supported.
    // First index is an element offset into the sealed index-buffer binding.
    bool draw_primitives(metal::uint vertexStart, metal::uint vertexCount,
                         metal::uint instanceCount = 1,
                         metal::uint baseInstance = 0) const thread {
        return draw(0, vertexStart, vertexCount, instanceCount, 0, baseInstance);
    }
    bool draw_indexed_primitives(index_type type, metal::uint firstIndex,
                                 metal::uint indexCount, metal::uint instanceCount,
                                 metal::int32_t baseVertex,
                                 metal::uint baseInstance) const thread {
        if (type != index_type::uint16 && type != index_type::uint32) {
            reset();
            return false;
        }
        return draw(metal::uint(type), firstIndex, indexCount, instanceCount,
                    baseVertex, baseInstance);
    }
    bool copy_command(const thread render_command &source) const thread {
        device KPRenderStateCommandRecord *dst = record();
        if (!dst) return false;
        device KPRenderStateCommandRecord *src = source.record();
        if (!src || source.buffer.records != buffer.records ||
            source.buffer.capacity != buffer.capacity ||
            src->magic != KP_RENDER_STATE_COMMAND_MAGIC) {
            reset();
            return false;
        }
        // Ordered single-writer copy; this introduces no cross-thread fence.
        KPRenderStateCommandRecord snapshot = *src;
        *dst = snapshot;
        return true;
    }
};
} // namespace keplermetal
