// SPDX-License-Identifier: MIT
// Controlled CPU fixture: registers resemble the watched checkpoints, but
// this code is original and does not reproduce or execute AppleGVA.
.text
.p2align 4, 0x90
.globl _kp_invoke
_kp_invoke:
    pushq %rbx
    pushq %r12
    pushq %r13
    movq %rdi, %rbx
    movq %rsi, %r12
    movl %edx, %r13d
    movq %r12, %rax
    callq _kp_classify
    testl %r13d, %r13d
    jnz 1f
    movq %r12, %rax
    callq _kp_skip
1:  callq _kp_after_enumeration
    popq %r13
    popq %r12
    popq %rbx
    retq
.subsections_via_symbols
