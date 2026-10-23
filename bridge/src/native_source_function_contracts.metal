// SPDX-License-Identifier: MIT
// Reflection-only refusal fixtures. Never submit these kernels to the GPU.
#include <metal_stdlib>
using namespace metal;
struct Context { uint magic,version,capacity,max_bindings; ulong records_address; uint record_bytes,pipeline_count; };
struct WrongContext { uint magic,version,capacity,max_bindings; long records_address; uint record_bytes,pipeline_count; };
struct LongContext { uint magic,version,capacity,max_bindings; ulong records_address; uint record_bytes,pipeline_count; ulong extra; };
#define TAIL device uint *a [[id(2)]]; device uint *b [[id(3)]]; device uint *c [[id(4)]]; device uint *d [[id(5)]];
struct WrongToken { device Context *commands [[id(0)]]; uint pipeline [[id(1)]]; TAIL };
struct WrongContextType { device WrongContext *commands [[id(0)]]; ulong pipeline [[id(1)]]; TAIL };
struct WrongContextSize { device LongContext *commands [[id(0)]]; ulong pipeline [[id(1)]]; TAIL };
struct WrongContextAccess { device const Context *commands [[id(0)]]; ulong pipeline [[id(1)]]; TAIL };
struct MissingContext { device uint *commands [[id(0)]]; ulong pipeline [[id(1)]]; TAIL };
struct MissingSlot { device Context *commands [[id(0)]]; ulong pipeline [[id(1)]]; device uint *a [[id(2)]]; device uint *b [[id(3)]]; };
struct ExtraSlot { device Context *commands [[id(0)]]; ulong pipeline [[id(1)]]; TAIL device uint *extra [[id(6)]]; };
#define FIXTURE(NAME,TYPE) kernel void NAME(device TYPE &args [[buffer(0)]]) { args.a[0]=args.commands->magic; }
FIXTURE(wrong_token,WrongToken)
FIXTURE(wrong_context_type,WrongContextType)
FIXTURE(wrong_context_size,WrongContextSize)
FIXTURE(wrong_context_access,WrongContextAccess)
kernel void missing_context(device MissingContext &args [[buffer(0)]]) { args.a[0]=args.commands[0]; }
FIXTURE(missing_slot,MissingSlot)
FIXTURE(extra_slot,ExtraSlot)
