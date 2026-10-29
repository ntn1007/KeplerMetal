// SPDX-License-Identifier: MIT
.text
.p2align 4, 0x90
.globl _kp_invoke_after_dispatch
_kp_invoke_after_dispatch:
    pushq %r12
    pushq %r13
    pushq %r14
    movq %rdi, %r12
    movl %esi, %r13d
    movl %edx, %r14d
    movl %r13d, %eax
    callq _kp_after_dispatch
    testl %r14d, %r14d
    jnz 1f
    callq _kp_failure_path
    jmp 2f
1:  callq _kp_nonempty_path
2:  popq %r14
    popq %r13
    popq %r12
    retq
.subsections_via_symbols
