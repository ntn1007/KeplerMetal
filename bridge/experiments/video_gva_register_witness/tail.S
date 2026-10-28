// SPDX-License-Identifier: MIT
// Experimental x86_64 tail and known-ABI CPU controls. Never executes vendor code.
.private_extern _KPAllocActive, _KPAllocExpected, _KPAllocCount, _KPAllocDropped, _KPAllocInflight
.private_extern _KPAllocRecords, _KPAllocOriginal
.text
.p2align 4, 0x90
.globl _KPAllocTail
_KPAllocTail:
    pushfq
    pushq %r11
    pushq %rax
    lock incq _KPAllocInflight(%rip)
    cmpq $0, _KPAllocActive(%rip)
    je Ltail_exit
    movq 24(%rsp), %r11
    cmpq _KPAllocExpected(%rip), %r11
    jne Ltail_exit
    movq $1, %r11
    lock xaddq %r11, _KPAllocCount(%rip)
    cmpq $64, %r11
    jae Ltail_drop
    shlq $7, %r11
    leaq _KPAllocRecords(%rip), %rax
    addq %r11, %rax
    movq %r14, 0(%rax)
    movq %rdi, 8(%rax)
    movq 24(%rsp), %r11
    movq %r11, 64(%rax)
    movq $1, 104(%rax)
    jmp Ltail_exit
Ltail_drop:
    lock incq _KPAllocDropped(%rip)
Ltail_exit:
    lock decq _KPAllocInflight(%rip)
    popq %rax
    popq %r11
    popfq
    jmpq *_KPAllocOriginal(%rip)


.subsections_via_symbols
