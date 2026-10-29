// SPDX-License-Identifier: MIT
.text
.globl _KMRun
_KMRun:
 pushq %rbp
 movq %rsp,%rbp
 pushq %r12
 pushq %r14
 pushq %r15
 pushq %rbx
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
 movq %rax,-0x1a0(%rbp)
 testq %rax,%rax
 jz Ldone
 movq %r14,%rdi
.globl _KMBeforeFilter
_KMBeforeFilter:
 callq _KMFilter
.globl _KMAfterFilter
_KMAfterFilter:
 testq %rax,%rax
 jz Ldone
 movq %rax,%r15
 movq %r15,%rdi
 callq _KMGetReg
.globl _KMAfterReg
_KMAfterReg:
 movq %rax,-0x1a8(%rbp)
 movq %r15,%rdi
 callq _KMGetName
.globl _KMAfterName
_KMAfterName:
 movq %rax,-0x1b8(%rbp)
 leaq _KMMap(%rip),%rdi
 movq _KMKeyForSet(%rip),%rsi
 movq _KMValueForSet(%rip),%rdx
.globl _KMBeforeSet
_KMBeforeSet:
 callq _KMSet
.globl _KMAfterSet
_KMAfterSet:
 movq -0x1b8(%rbp),%rax
 movq %rax,%rbx
 movq %rax,%rdi
 leaq _KMIGPU(%rip),%rsi
.globl _KMBeforeCompare
_KMBeforeCompare:
 callq _KMCompare
.globl _KMAfterCompare
_KMAfterCompare:
 movb %al,%bl
 callq _KMNextBatch
.globl _KMAfterNext
_KMAfterNext:
 nop
.globl _KMBranchTest
_KMBranchTest:
 testb %bl,%bl
 jz Lzero
.globl _KMPathNonzero
_KMPathNonzero:
 jmp Ldone
Lzero:
.globl _KMPathZero
_KMPathZero:
 nop
Ldone:
 movq -0x1a0(%rbp),%rax
 addq $0x1b0,%rsp
 popq %rbx
 popq %r15
 popq %r14
 popq %r12
 popq %rbp
 retq
.globl _KMFilter
_KMFilter:
 pushq %rbp
 movq %rsp,%rbp
 callq _KMGetDict
.globl _KMAfterDict
_KMAfterDict:
 popq %rbp
 retq
.subsections_via_symbols
