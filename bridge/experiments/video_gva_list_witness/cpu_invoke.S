// SPDX-License-Identifier: MIT
// Keep an explicit test pointer in the same callee-saved register as the
// studied AppleGVA callsite. The callee itself does not dereference it.
.text
.p2align 4, 0x90
.globl _kp_invoke_after_enumeration
_kp_invoke_after_enumeration:
    pushq %rbx
    movq %rdi, %rbx
    movq %rsi, %rax
    movl $2, %edi
    callq _kp_list_entry
    callq _kp_after_enumeration
    popq %rbx
    retq
.subsections_via_symbols
