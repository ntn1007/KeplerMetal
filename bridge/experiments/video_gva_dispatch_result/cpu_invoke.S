// SPDX-License-Identifier: MIT
.text
.p2align 4, 0x90
.globl _kp_invoke_after_enumeration
_kp_invoke_after_enumeration:
    pushq %rbx
    pushq %r12
    subq $8, %rsp
    movq %rdi, %rbx
    movl %esi, %r12d
    callq _kp_after_enumeration
    movl %r12d, %eax
    callq _kp_return_ready
    addq $8, %rsp
    popq %r12
    popq %rbx
    retq
.subsections_via_symbols
