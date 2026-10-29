// SPDX-License-Identifier: MIT
.text
.globl _KMRun
_KMRun:
 pushq %rbp
 movq %rsp,%rbp
 pushq %r12
 subq $8,%rsp
 callq _KMGetList
.globl _KMAfterList
_KMAfterList:
 movq %rax,%r12
 movq %rax,%rdi
 callq _KMGetBatch
.globl _KMAfterBatch
_KMAfterBatch:
 addq $8,%rsp
 popq %r12
 popq %rbp
 retq
.subsections_via_symbols
