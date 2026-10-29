// SPDX-License-Identifier: MIT
.text
.globl _KMRun
_KMRun:
 pushq %rbp
 movq %rsp,%rbp
 pushq %r12
 pushq %r14
 subq $0x1b0,%rsp
 leaq _KMDevice(%rip),%r14
 movq %r14,%rdi
 callq _KMGetRegistry
.globl _KMAfterRegistry
_KMAfterRegistry:
 movq %r14,-0x1b0(%rbp)
 leaq -0x1b0(%rbp),%rax
 movq %rax,-0x198(%rbp)
 callq _KMGetList
.globl _KMAfterList
_KMAfterList:
 movq %rax,%r12
 movq %rax,%rdi
 callq _KMGetBatch
.globl _KMAfterBatch
_KMAfterBatch:
 addq $0x1b0,%rsp
 popq %r14
 popq %r12
 popq %rbp
 retq
.subsections_via_symbols
