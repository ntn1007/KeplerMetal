// SPDX-License-Identifier: MIT
#include <metal_stdlib>
#include "KeplerNativeRenderCommands.h"
using namespace metal;
using namespace keplermetal;

static bool empty_record(device const KPRenderStateCommandRecord *r) {
    device const uint *words = reinterpret_cast<device const uint *>(r);
    bool empty = true;
    for (uint i = 0; i < 16; i++) empty &= words[i] == 0u;
    return empty;
}

// Same input recipe as the raw-record reference. A single writer stages each
// completed command in slot 2, copies it, then resets the staging slot.
kernel void generate_render_state_records(device const uint *input [[buffer(0)]],
    device uint *range [[buffer(1)]], device uint *counter [[buffer(2)]],
    constant uint4 &config [[buffer(3)]],
    device const KPRenderStateIdentity *identities [[buffer(4)]],
    device KPRenderStateCommandRecord *records [[buffer(5)]],
    device const KPRenderStateIdentity *foreignIdentities [[buffer(6)]],
    uint lane [[thread_position_in_grid]]) {
    if (lane) return;
    render_command_buffer buffer{records, 4};
    uint value = input[(config.x * 5u + 3u) % 16u];
    bool ok = true;
    keplermetal::render_command draft(buffer, 2);
    for (uint slot = 0; slot < 4; slot++) {
        keplermetal::render_command destination(buffer, slot);
        ok &= destination.reset();
        if (slot == 2) continue;
        uint kind = slot == 0 ? 0 : slot == 1 ? 1 : 2;
        uint choice = config.w ? config.w - 1u : (value >> (kind + 3u)) & 1u;
        ok &= draft.reset();
        ok &= draft.set_render_state(identities[choice]);
        uint first = (slot == 0 ? 5u : 0u) + 3u * ((value >> kind) & 1u);
        if (slot == 0) ok &= draft.draw_primitives(first, 3);
        else ok &= draft.draw_indexed_primitives(
            slot == 1 ? index_type::uint16 : index_type::uint32,
            first, 3, 1, slot == 1 ? 2 : -2, slot == 1 ? 1 : 2);
        ok &= draft.copy_command(draft);
        ok &= destination.copy_command(draft);
        ok &= draft.reset();
        // Deliberately malformed wire controls retain the previous independent
        // oracle. The source interface does not authorize unknown identities.
        if (config.y == 1u && slot == 1u) records[slot].state_identity = 0ul;
        if (config.y == 2u && slot == 3u) records[slot].state_identity = foreignIdentities[choice];
        if (config.y == 3u && slot == 0u) records[slot].kind = 1u;
        if (config.y == 4u && slot == 1u) records[slot].arguments[2] = 0xfffffffeu;
        if (config.y == 5u && slot == 3u) records[slot].reserved[0] = 1u;
        if (config.y == 6u && slot == 0u) records[slot].state_identity ^= 0x100000000ul;
    }
    // Invalid destinations must never touch the surrounding record guards.
    keplermetal::render_command outside(buffer, 4), tooLarge({records, 17}, 0), null({nullptr, 4}, 0);
    ok &= !outside.reset() && !outside.set_render_state(identities[0]) &&
          !outside.draw_primitives(0, 3) && !tooLarge.reset() && !null.reset();
    // Failed copies and unsupported index types clear a previously valid
    // destination, preventing a stale draw. Different-capacity aliases refuse.
    ok &= draft.set_render_state(identities[0]) && draft.draw_primitives(5, 3);
    ok &= !draft.copy_command(outside);
    ok &= empty_record(records + 2);
    ok &= draft.set_render_state(identities[0]) && draft.draw_primitives(5, 3);
    keplermetal::render_command wrongCapacity({records, 3}, 0);
    ok &= !draft.copy_command(wrongCapacity);
    ok &= empty_record(records + 2);
    ok &= draft.set_render_state(identities[0]) && draft.draw_primitives(5, 3);
    ok &= !draft.draw_indexed_primitives(index_type(42), 0, 3, 1, 0, 0);
    ok &= empty_record(records + 2);
    range[0] = 0; range[1] = 4;
    counter[0] = (value ^ 0x4b505357u) ^ (ok ? 0u : 1u);
}
