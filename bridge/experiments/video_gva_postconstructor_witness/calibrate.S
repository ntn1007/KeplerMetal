// SPDX-License-Identifier: MIT
.private_extern _KPMockR14, _KPMockArgs, _KPMockStackArg, _KPMockFlags, _KPMockRax, _KPMockR10, _KPMockR11
.text
// Each control passes the same arguments and known stack word; only the
// return address and whether the tail is used differ. Flags are set last.
.macro invoke name, target, return_label
.p2align 4, 0x90
.globl _\name
_\name:
    pushq %r14
    movq %rdi, %r14
    movq %rsi, %rax
    subq $8, %rsp
    pushq $0x77
    pushq %rax
    popfq
    movq $0x600, %rdi
    movq $0x22, %rsi
    movq $0x33, %rdx
    movq $0x44, %rcx
    movq $0x55, %r8
    movq $0x66, %r9
    movq $0x88, %r10
    movq $0x99, %r11
    movq $0xaa, %rax
    callq _\target
.globl _\return_label
_\return_label:
    leaq 16(%rsp), %rsp
    popq %r14
    retq
.endm
invoke KPInvokeNative, KPMockOriginal, KPInvokeNativeReturn
invoke KPInvokeMatch, KPAllocTail, KPInvokeMatchReturn
invoke KPInvokeMiss, KPAllocTail, KPInvokeMissReturn

// Actual public C++ nothrow allocation ABI: the caller supplies the address
// of std::nothrow. The return is a real allocation to be released by the test.
.p2align 4, 0x90
.globl _KPInvokeAllocator
_KPInvokeAllocator:
    pushq %r14
    movq %rdi, %r14
    movq $0x600, %rdi
    callq _KPAllocTail
.globl _KPInvokeAllocatorReturn
_KPInvokeAllocatorReturn:
    popq %r14
    retq

.p2align 4, 0x90
.globl _KPMockOriginal
_KPMockOriginal:
    movq %r14, _KPMockR14(%rip)
    movq %rdi, _KPMockArgs+0(%rip)
    movq %rsi, _KPMockArgs+8(%rip)
    movq %rdx, _KPMockArgs+16(%rip)
    movq %rcx, _KPMockArgs+24(%rip)
    movq %r8, _KPMockArgs+32(%rip)
    movq %r9, _KPMockArgs+40(%rip)
    movq %rax, _KPMockRax(%rip)
    movq %r10, _KPMockR10(%rip)
    movq %r11, _KPMockR11(%rip)
    movq 8(%rsp), %rax
    movq %rax, _KPMockStackArg(%rip)
    pushfq
    popq %rax
    movq %rax, _KPMockFlags(%rip)
    movabsq $0x3141592653589793, %rax
    retq
.subsections_via_symbols
