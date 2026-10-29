// SPDX-License-Identifier: MIT
.text
.p2align 4, 0x90
.globl _kp_cache_invoke
_kp_cache_invoke:
    movq %rdi, %rax
    subq $8, %rsp
    callq _kp_cache_target
    addq $8, %rsp
    retq
.p2align 4, 0x90
.globl _kp_cache_target
_kp_cache_target:
    .rept 8
    nop
    .endr
    retq
.subsections_via_symbols
