// SPDX-License-Identifier: MIT
.text
.p2align 4, 0x90
.globl _kp_invoke_error_path
_kp_invoke_error_path:
    pushq %r12
    movl %edi, %r12d
    callq _kp_failure_path
    movl %r12d, %eax
    callq _kp_gva_exit
    movl %r12d, %eax
    callq _kp_vt_return
    popq %r12
    retq
.subsections_via_symbols
