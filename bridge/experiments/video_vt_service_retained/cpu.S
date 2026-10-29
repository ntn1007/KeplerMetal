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
 movl $1234,%r15d
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
 jmp Lapply
Lzero:
.globl _KMPathZero
_KMPathZero:
 nop
Lapply:
 leaq _KMMap(%rip),%rdi
 leaq _KMCallbackEntry(%rip),%rsi
 leaq -0x1c0(%rbp),%rdx
.globl _KMBeforeApply
_KMBeforeApply:
 callq _KMApplyFunction
 leaq -0x1c0(%rbp),%r12
 cmpl $0,_KMOutputWrong(%rip)
 je LcorrectOut
 leaq -0x1b0(%rbp),%r12
LcorrectOut:
 leaq -0x1c8(%rbp),%rbx
 xorl %r15d,%r15d
.globl _KMBeforeOutStore
_KMBeforeOutStore:
 movq %r12,(%rbx)
.globl _KMAfterOutStore
_KMAfterOutStore:
 movq %r12,%rdi
.globl _KMBeforeCount
_KMBeforeCount:
 callq _KMArrayCount
.globl _KMAfterCount
_KMAfterCount:
 movq %r12,%rdi
 xorl %esi,%esi
.globl _KMBeforeItem
_KMBeforeItem:
 callq _KMArrayItem
.globl _KMAfterItem
_KMAfterItem:
 movq %rax,%rdi
 movq _KMRequest(%rip),%rsi
 xorl %edx,%edx
.globl _KMBeforeRequestFilter
_KMBeforeRequestFilter:
 callq _KMRequestFilter
.globl _KMAfterRequestFilter
_KMAfterRequestFilter:
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
.globl _KMRequestFilter
_KMRequestFilter:
 pushq %rbp
 movq %rsp,%rbp
 pushq %r14
 pushq %r15
 movq %rdi,%r14
 movq %rsi,%r15
 leaq _KMFirstKey(%rip),%rsi
.globl _KMFirstInput
_KMFirstInput:
 callq _KMFirst
.globl _KMFirstResult
_KMFirstResult:
 testq %rax,%rax
 jz LprobeAbsent
 movq %rax,%rdi
 movq %r15,%rsi
 callq _KMSecond
.globl _KMSecondResult
_KMSecondResult:
 testq %rax,%rax
 jnz LprobeYes
LprobeAbsent:
 movq %r14,%rdi
 leaq _KMAbsentKey(%rip),%rsi
 callq _KMAbsent
.globl _KMAbsentResult
_KMAbsentResult:
 testq %rax,%rax
 jz LprobeService
 movq %rax,%rdi
 callq _KMContains
.globl _KMContainsResult
_KMContainsResult:
 testb %al,%al
 jnz LprobeNo
LprobeService:
 movq %r14,%rdi
 leaq _KMServiceKey(%rip),%rsi
 callq _KMService
.globl _KMServiceResult
_KMServiceResult:
 testb %al,%al
 jz LprobeNo
 movl $1234,%edi
 cmpl $0,_KMServiceWrong(%rip)
 je LserviceCorrect
 movl $1235,%edi
LserviceCorrect:
 leaq _KMPlane(%rip),%rsi
 movq %r15,%rdx
 xorl %ecx,%ecx
 movl $1,%r8d
.globl _KMPropertyInput
_KMPropertyInput:
 callq _KMProperty
.globl _KMPropertyResult
_KMPropertyResult:
 testq %rax,%rax
 jz LprobeNo
LprobeYes:
 movl $1,%eax
 jmp LprobeExit
LprobeNo:
 xorl %eax,%eax
LprobeExit:
 popq %r15
 popq %r14
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
.globl _KMCallbackEntry
_KMCallbackEntry:
 pushq %rbp
 movq %rsp,%rbp
 pushq %r14
 pushq %r15
 pushq %rbx
 subq $8,%rsp
 movq %rdx,%r14
 movq %rsi,%rbx
 leaq -0x20(%rbp),%r15
 movb $0,(%r15)
 movq %rbx,%rdi
 movq %r15,%rsi
 callq _KMGetAvailable
.globl _KMAfterAvailable
_KMAfterAvailable:
 cmpb $0,(%r15)
 je LcallbackDone
 movq %r14,%rdi
 movq %rbx,%rsi
.globl _KMBeforeAppend
_KMBeforeAppend:
 callq _KMAppend
.globl _KMAfterAppend
_KMAfterAppend:
LcallbackDone:
 addq $8,%rsp
 popq %rbx
 popq %r15
 popq %r14
 popq %rbp
 retq
.section __TEXT,__cstring,cstring_literals
.globl _KMPlane
_KMPlane:
.asciz "IOService"
.subsections_via_symbols
