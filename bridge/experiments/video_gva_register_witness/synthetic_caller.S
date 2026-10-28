// SPDX-License-Identifier: MIT
// Separate image: call the public nothrow allocator with an r14 test value.
.text
.macro caller name, done
.globl _\name
_\name:
    pushq %r14
    movq %rdi,%r14
    movq $0x600,%rdi
    callq __ZnwmRKSt9nothrow_t
.globl _\done
_\done:
    popq %r14
    retq
.endm
caller KPSyntheticMatch,KPSyntheticMatchReturn
caller KPSyntheticMiss,KPSyntheticMissReturn
.subsections_via_symbols
