// SPDX-License-Identifier: MIT
.text
.p2align 4, 0x90
.globl _KPTraceHeapTarget
_KPTraceHeapTarget:
    .rept 8
    nop
    .endr
    retq
.subsections_via_symbols
