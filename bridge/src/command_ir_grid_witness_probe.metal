#include <metal_stdlib>
using namespace metal;
// Test-only: change shader-visible group counts, leaving QMD, addresses,
// launch dimensions and all other constants untouched.
kernel void override_grid_witness(device uint *constants [[buffer(0)]],
 constant uint &groups [[buffer(1)]],uint lane [[thread_position_in_grid]]) {
 if(lane==0u){constants[0x740u/4u]=groups;constants[0x744u/4u]=1u;constants[0x748u/4u]=1u;}
}
