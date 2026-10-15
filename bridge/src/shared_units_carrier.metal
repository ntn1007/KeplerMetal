#include <metal_stdlib>
using namespace metal;
#ifndef SHARED_WORDS
#define SHARED_WORDS 4096
#endif
struct SharedParameters {ulong outputAddress;uint seed,active,variant,operand;};
constant uint groupKey=0x00100001u;
constant uint phaseKey=0x6a09e667u;
constant uint controlKey=0xabad1deau;
template<bool Control>
static void capacity_body(threadgroup uint *shared,device uint *output,
                          constant SharedParameters &p,uint tid,uint group,uint local) {
    uint groupSeed=p.seed^(group*groupKey);
    for(uint i=tid;i<SHARED_WORDS;i+=local)shared[i]=(i*0x9e3779b9u)^groupSeed;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    for(uint i=tid;i<SHARED_WORDS;i+=local)
        output[group*(2*SHARED_WORDS)+i]=shared[(i*5+7)%SHARED_WORDS]^(Control?controlKey:0u);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    for(uint i=tid;i<SHARED_WORDS;i+=local)shared[i]=((i*0x9e3779b9u)^groupSeed)^phaseKey;
    threadgroup_barrier(mem_flags::mem_threadgroup);
    for(uint i=tid;i<SHARED_WORDS;i+=local)
        output[group*(2*SHARED_WORDS)+SHARED_WORDS+i]=shared[(i*7+13)%SHARED_WORDS]^(Control?controlKey:0u);
}
#define CAPACITY_KERNEL(NAME,CONTROL) \
kernel void NAME(constant SharedParameters &p [[buffer(0)]],device uint *output [[buffer(1)]], \
                 uint tid [[thread_index_in_threadgroup]],uint group [[threadgroup_position_in_grid]], \
                 uint local [[threads_per_threadgroup]]) { \
    threadgroup uint shared[SHARED_WORDS]; \
    capacity_body<CONTROL>(shared,output,p,tid,group,local); \
}
CAPACITY_KERNEL(shared_capacity_carrier,true)
CAPACITY_KERNEL(shared_capacity_control,true)
CAPACITY_KERNEL(shared_capacity_reference,false)

template<uint Op,bool Control>
static void atomic_body(threadgroup atomic_uint *counter,device uint *output,
                        constant SharedParameters &p,uint tid,uint group,uint local) {
    uint initial=p.seed+group*groupKey;
    if(tid==0)atomic_store_explicit(counter,initial,memory_order_relaxed);
    threadgroup_barrier(mem_flags::mem_threadgroup);
    // This serialized load/compare/store oracle does not call Metal weak CAS:
    // that separate native shader failed readback with Invalid Resource.
    // The NAK CAS under test remains contended and uses hardware ld/st locks.
    if(Op==2) {
        for(uint writer=0;writer<p.active;writer++) {
            if(tid==writer) {
                uint compare=initial^(p.variant?1u:0u);
                uint replacement=p.operand^(Control?controlKey:0u);
                uint previous=atomic_load_explicit(counter,memory_order_relaxed);
                if(previous==compare)atomic_store_explicit(counter,replacement,memory_order_relaxed);
                output[group*(local+1)+tid]=previous;
            }
            threadgroup_barrier(mem_flags::mem_threadgroup);
        }
    } else if(tid<p.active) {
        uint previous;
        if(Op==0)previous=atomic_fetch_add_explicit(counter,Control?2u:1u,memory_order_relaxed);
        else if(Op==1)previous=atomic_exchange_explicit(counter,(p.operand^tid)^(Control?controlKey:0u),memory_order_relaxed);
        else previous=0;
        output[group*(local+1)+tid]=previous;
    }
    threadgroup_barrier(mem_flags::mem_threadgroup);
    if(tid==0)output[group*(local+1)+local]=atomic_load_explicit(counter,memory_order_relaxed);
}
#define ATOMIC_KERNEL(NAME,OP,CONTROL) \
kernel void NAME(constant SharedParameters &p [[buffer(0)]],device uint *output [[buffer(1)]], \
                 uint tid [[thread_index_in_threadgroup]],uint group [[threadgroup_position_in_grid]], \
                 uint local [[threads_per_threadgroup]]) { \
    threadgroup atomic_uint counter; \
    atomic_body<OP,CONTROL>(&counter,output,p,tid,group,local); \
}
ATOMIC_KERNEL(shared_add_carrier,0,true)
ATOMIC_KERNEL(shared_add_control,0,true)
ATOMIC_KERNEL(shared_add_reference,0,false)
ATOMIC_KERNEL(shared_exchange_carrier,1,true)
ATOMIC_KERNEL(shared_exchange_control,1,true)
ATOMIC_KERNEL(shared_exchange_reference,1,false)
ATOMIC_KERNEL(shared_cas_carrier,2,true)
ATOMIC_KERNEL(shared_cas_control,2,true)
ATOMIC_KERNEL(shared_cas_reference,2,false)
