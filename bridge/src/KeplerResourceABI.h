// Observed GeForceMTLDriver 16 profile on this GTX 880M, not a general Apple ABI.
// Values come from unmodified native shaders and are qualified by GPU fixtures.
#pragma once
enum {
    KP_RESOURCE_CB = 1,
    KP_RESOURCE_STRIDE = 32,
    KP_RESOURCE_ADDRESS_OFFSET = 8,
    KP_UNIFORM_CB = 2,
    KP_INSTANCE_BASE_OFFSET = 0x6c4,
    KP_WORKGROUP_SIZE_OFFSET = 0x6f0,
    KP_GLOBAL_ORIGIN_OFFSET = 0x710,
    KP_GRID_THREADS_OFFSET = 0x720,
    KP_THREADGROUP_COUNT_OFFSET = 0x740,
    KP_COMPUTE_TEXTURE0_HANDLE_OFFSET = 0x400,
    KP_SURFACE_TABLE_ADDRESS_OFFSET = 0x6e8,
    KP_SURFACE_DESCRIPTOR_STRIDE = 80,
    KP_SURFACE_ADDRESS_SHIFTED8_OFFSET = 0,
    KP_SURFACE_FORMAT_OFFSET = 4,
    KP_SURFACE_CLAMP_X_OFFSET = 8,
    KP_SURFACE_PITCH_OFFSET = 12,
    KP_SURFACE_CLAMP_Y_OFFSET = 16,
};
static inline unsigned KPResourceAddressOffset(unsigned binding) {
    return KP_RESOURCE_ADDRESS_OFFSET + KP_RESOURCE_STRIDE * binding;
}
