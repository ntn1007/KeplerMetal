#include <metal_stdlib>
using namespace metal;
// Buffer-only evaluation isolates shader arithmetic from raster interpolation.
[[patch(triangle,3)]]
vertex void tess_capture(float3 coord [[position_in_patch]],
                        device atomic_uint *counter [[buffer(0)]],
                        device float4 *coordinates [[buffer(1)]],
                        device float4 *values [[buffer(2)]]) {
    uint index = atomic_fetch_add_explicit(counter, 1u, memory_order_relaxed);
    if (index < 32768u) {
        coordinates[index] = float4(coord, 1);
        values[index] = float4(coord * coord, 1);
    }
}
