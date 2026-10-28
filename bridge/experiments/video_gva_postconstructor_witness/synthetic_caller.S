// SPDX-License-Identifier: MIT
// Separate image: call the public deallocator with an r14 test value.
.text
.macro caller name, done
.globl _\name
_\name:
    pushq %r14
    movq %rdi,%r14
    movq %rsi,%rdi
    callq __ZdlPv
.globl _\done
_\done:
    popq %r14
    retq
.endm
caller KPSyntheticMatch,KPSyntheticMatchReturn
caller KPSyntheticMiss,KPSyntheticMissReturn
.subsections_via_symbols
