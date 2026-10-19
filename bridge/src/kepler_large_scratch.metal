// SPDX-License-Identifier: MIT
// Uniform full workgroups only: the pressure kernels contain a device barrier.
#include <metal_stdlib>
using namespace metal;
struct LocalParams { uint seed, count, stride, reserved; };
static uint rol5(uint x) { return (x << 5) | (x >> 27); }

template<uint Words>
static uint4 local_work(volatile device const uint *input, constant LocalParams &p, uint gid) {
    volatile thread uint scratch[Words];
    uint state = input[gid * p.stride] ^ p.seed ^ (gid * 747796405u);
    for (uint i = 0; i < Words; ++i)
        scratch[i] = (state + i * 2891336453u) ^ (i * 22695477u + 0x11998877u);
    for (uint round = 0; round < 17; ++round) {
        uint index = (state ^ (round * 97u)) & (Words - 1);
        uint other = (index + 13u) & (Words - 1);
        uint a = scratch[index], b = scratch[other];
        uint next = rol5(a ^ b) + (state ^ round);
        scratch[index] = next;
        state = (next * 1664525u + 1013904223u) ^ b;
    }
    uint checksum = state;
    for (uint i = 0; i < Words; ++i) checksum = rol5(checksum ^ scratch[i]) + i;
    return uint4(checksum, state, Words, 0xcafe0000u ^ gid);
}

#define LOCAL_KERNEL(NAME, WORDS) \
kernel void NAME(volatile device const uint *input [[buffer(0)]], \
                 device uint4 *output [[buffer(1)]], \
                 constant LocalParams &p [[buffer(2)]], uint gid [[thread_position_in_grid]]) { \
    if (gid < p.count) output[gid] = local_work<WORDS>(input, p, gid); \
}
LOCAL_KERNEL(local32, 32)
LOCAL_KERNEL(local256, 256)
LOCAL_KERNEL(local1024, 1024)

kernel void local_control(volatile device const uint *input [[buffer(0)]],
                          device uint4 *output [[buffer(1)]],
                          constant LocalParams &p [[buffer(2)]], uint gid [[thread_position_in_grid]]) {
    if (gid < p.count) {
        uint state = input[gid * p.stride] ^ p.seed ^ (gid * 747796405u);
        output[gid] = uint4(rol5(state), state, 0, 0xcafe0000u ^ gid);
    }
}

// Named scalar SSA values, rather than an explicitly indexed thread array.
// A volatile key is loaded after the barrier; the dependent nonlinear fold
// prevents reducing all live input values before that load. Disassembly must
// establish actual spilling; source-level pressure alone is not proof.
#define LIVE32(X) \
 X(0) X(1) X(2) X(3) X(4) X(5) X(6) X(7) \
 X(8) X(9) X(10) X(11) X(12) X(13) X(14) X(15) \
 X(16) X(17) X(18) X(19) X(20) X(21) X(22) X(23) \
 X(24) X(25) X(26) X(27) X(28) X(29) X(30) X(31)
#define LIVE64(X) LIVE32(X) \
 X(32) X(33) X(34) X(35) X(36) X(37) X(38) X(39) \
 X(40) X(41) X(42) X(43) X(44) X(45) X(46) X(47) \
 X(48) X(49) X(50) X(51) X(52) X(53) X(54) X(55) \
 X(56) X(57) X(58) X(59) X(60) X(61) X(62) X(63)
#define LIVE96(X) LIVE64(X) \
 X(64) X(65) X(66) X(67) X(68) X(69) X(70) X(71) \
 X(72) X(73) X(74) X(75) X(76) X(77) X(78) X(79) \
 X(80) X(81) X(82) X(83) X(84) X(85) X(86) X(87) \
 X(88) X(89) X(90) X(91) X(92) X(93) X(94) X(95)
#define LOAD_VALUE(I) uint v##I = input[base + I];
#define FOLD_VALUE(I) checksum = rol5(checksum ^ v##I) + (key ^ ((I) * 2891336453u));
#define PRESSURE_KERNEL(NAME, LIST, WORDS) \
kernel void NAME(volatile device const uint *input [[buffer(0)]], \
                 device uint4 *output [[buffer(1)]], \
                 constant LocalParams &p [[buffer(2)]], uint gid [[thread_position_in_grid]]) { \
    uint base = gid * p.stride; \
    LIST(LOAD_VALUE) \
    threadgroup_barrier(mem_flags::mem_device); \
    uint key = input[base + 128] ^ p.seed; \
    uint checksum = key ^ gid; \
    LIST(FOLD_VALUE) \
    output[gid] = uint4(checksum, key, WORDS, 0xcafe0000u ^ gid); \
}
PRESSURE_KERNEL(pressure32, LIVE32, 32)
PRESSURE_KERNEL(pressure64, LIVE64, 64)
PRESSURE_KERNEL(pressure96, LIVE96, 96)

// Additional paired source cases; semantic reference, not a physical frame claim.
LOCAL_KERNEL(local2048, 2048)
LOCAL_KERNEL(local4096, 4096)
