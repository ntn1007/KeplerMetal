// SPDX-License-Identifier: MIT
// Separate empty function: the entry register carries a base without patching
// the target's code, and may be observed by a hardware breakpoint.
.text
.p2align 4, 0x90
.globl _KPGVAReady
_KPGVAReady:
    retq
.subsections_via_symbols
