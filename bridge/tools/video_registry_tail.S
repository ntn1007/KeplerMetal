// SPDX-License-Identifier: MIT
// No C calls, opaque argument reads, FP/vector instructions or return substitution.
#include "video_registry_layout.h"
.set KPREG_CAPACITY_ASM, KPREG_CAPACITY
.set KPREG_SHIFT_ASM, KPREG_STRIDE_SHIFT
.private_extern _KPRegistryActive, _KPRegistryInflight, _KPRegistryCount, _KPRegistryDropped
.private_extern _KPRegistryRecords
.private_extern _KPRegistryO0, _KPRegistryO1, _KPRegistryO2, _KPRegistryO3, _KPRegistryO4, _KPRegistryO5
.text
.macro KPREG_TAIL function, number, original
.p2align 4, 0x90
.globl _\function
_\function:
    pushfq
    pushq %r11
    pushq %rax
    lock incq _KPRegistryInflight(%rip)
    cmpq $0, _KPRegistryActive(%rip)
    je Lexit\@
    movq $1, %r11
    lock xaddq %r11, _KPRegistryCount(%rip)
    cmpq $KPREG_CAPACITY_ASM, %r11
    jae Ldrop\@
    shlq $KPREG_SHIFT_ASM, %r11
    leaq _KPRegistryRecords(%rip), %rax
    addq %r11, %rax
    movq $\number, 0(%rax)
    movq %rdi, 8(%rax)
    movq %rsi, 16(%rax)
    movq %rdx, 24(%rax)
    movq %rcx, 32(%rax)
    movq %r8, 40(%rax)
    movq %r9, 48(%rax)
    movq 24(%rsp), %r11
    movq %r11, 56(%rax)
    movq 0(%rsp), %r11
    movq %r11, 64(%rax)
    movq 16(%rsp), %r11
    movq %r11, 72(%rax)
    leaq 24(%rsp), %r11
    movq %r11, 80(%rax)
    movq %r10, 88(%rax)
    movq 8(%rsp), %r11
    movq %r11, 96(%rax)
    movq $1, 104(%rax)
    jmp Lexit\@
Ldrop\@:
    lock incq _KPRegistryDropped(%rip)
Lexit\@:
    lock decq _KPRegistryInflight(%rip)
    popq %rax
    popq %r11
    popfq
    jmpq *_\original(%rip)
.endm
KPREG_TAIL KPRegistryTail0, 0, KPRegistryO0
KPREG_TAIL KPRegistryTail1, 1, KPRegistryO1
KPREG_TAIL KPRegistryTail2, 2, KPRegistryO2
KPREG_TAIL KPRegistryTail3, 3, KPRegistryO3
KPREG_TAIL KPRegistryTail4, 4, KPRegistryO4
KPREG_TAIL KPRegistryTail5, 5, KPRegistryO5

// These two original CPU-test functions have known, explicitly declared ABIs.
.p2align 4, 0x90
.globl _KPRegistryTestFlagsCall
_KPRegistryTestFlagsCall:
    movq %rdi, %r10
    pushq %rsi
    popfq
    jmpq *%r10
.p2align 4, 0x90
.globl _KPRegistryTestFlagsOriginal
_KPRegistryTestFlagsOriginal:
    pushfq
    popq %rax
    retq
.subsections_via_symbols
