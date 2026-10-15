#include <metal_stdlib>
using namespace metal;
// Laboratory mutation of one field in an already validated resident QMD.
// No program/resource/local/shared field is changed.
kernel void set_resident_qmd_grid(device uint *qmd [[buffer(0)]],
                                  constant uint &groups [[buffer(1)]]) {
    qmd[12]=groups;
}
