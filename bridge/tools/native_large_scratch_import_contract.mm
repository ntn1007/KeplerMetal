// SPDX-License-Identifier: MIT
// Constructor-only qualification. No queues, command buffers or GPU dispatches.
#import "KeplerProgramImport.h"
#import <objc/runtime.h>
#include <cstdio>

int main(int argc, char **argv) { @autoreleasepool {
 if (argc != 4) return 1;
 NSString *assets = @(argv[1]), *mode = @(argv[3]);
 BOOL old = [mode isEqual:@"old-reject"], negative = [mode isEqual:@"negative"];
 if (!old && !negative && ![mode isEqual:@"construct"]) return 1;
 id<MTLDevice> device = nil;
 for (id<MTLDevice> candidate in MTLCopyAllDevices())
  if (candidate.registryID == 4294968458 && [candidate.name isEqual:@"NVIDIA GeForce GTX 880M"]) device = candidate;
 if (!device) return 2;
 Method method = class_getInstanceMethod(objc_getClass("NVMTLFunctionVariant"), sel_registerName("initWithCompilerOutput:size:device:"));
 if (!method) return 2;
 IMP original = method_getImplementation(method);
 NSMutableArray *runs = [NSMutableArray new]; BOOL all = YES;
 NSData *library = [NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"local_memory.metallib"]];
 for (NSString *name in @[@"local2048", @"local4096"]) {
  NSDictionary *info = [NSJSONSerialization JSONObjectWithData:[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:[name stringByAppendingString:@".json"]]] options:0 error:nil];
  NSData *program = [NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:[name stringByAppendingString:@".sass"]]];
  unsigned frame = [name isEqual:@"local2048"] ? 8192 : 16384;
  if (!library.length || !program.length || ![info[@"semantic"] isEqual:name] || [info[@"scratch_bytes"] unsignedIntValue] != frame || [info[@"sm"] unsignedIntValue] != 30 || [info[@"crs_bytes"] unsignedIntValue] || [info[@"control_barriers"] unsignedIntValue]) return 2;
  unsigned first = negative ? 0 : 13;
  for (unsigned kind = first; kind <= 13; kind++) { @autoreleasepool {
   NSMutableData *lib = [library mutableCopy], *code = [program mutableCopy];
   NSData *libArg = lib, *codeArg = code; id<MTLDevice> target = device; NSString *function = name;
   KeplerLocalMemoryConfig config = {[info[@"registers"] unsignedIntValue], frame, frame, 0, 0};
   switch (kind) {
    case 0: ((unsigned char *)lib.mutableBytes)[0] ^= 1; break;
    case 1: config.required_scratch_bytes = frame + 4; break;
    case 2: config.carrier_local_bytes = frame + 4; break;
    case 3: config.carrier_spill_bytes = 4; break;
    case 4: config.carrier_control_barriers = 1; break;
    case 5: config.registers = 23; break;
    case 6: config.registers = 64; break;
    case 7: function = @"not_a_qualified_large_carrier"; break;
    case 8: [code setLength:code.length - 1]; break;
    case 9: libArg = nil; break;
    case 10: codeArg = nil; break;
    case 11: target = nil; break;
    case 12: [code setLength:0]; break;
   }
   NSError *error = nil; NSDictionary *proof = nil;
   id<MTLComputePipelineState> pipeline = KPCreateLocalMemoryPipeline(target, libArg, function, codeArg, config, &error, &proof);
   BOOL restored = method_getImplementation(method) == original;
   BOOL expectedRejection = old || kind != 13;
   BOOL pass = restored && (expectedRejection ? (!pipeline && error != nil) : (pipeline && error == nil && [proof[@"contract_verified"] boolValue] && ![proof[@"rejected_import"] boolValue]));
   if (old) pass = pass && [error.localizedDescription isEqual:@"Native local-memory carrier function is not qualified"];
   unsigned imports = 0;
   if (!expectedRejection) {
    for (NSDictionary *event in proof[@"events"]) if ([event[@"code_replaced"] boolValue]) {
     imports++;
     pass = pass && [event[@"native_local_metadata_verified"] boolValue] && [event[@"native_local_allocation_fields_preserved"] boolValue] && [event[@"native_metadata_preserved_except_instruction_register_and_control"] boolValue] && [event[@"imported_code_identical"] boolValue] && [event[@"code_input_unchanged_after_constructor"] boolValue] && [event[@"decoded_local_contract_verified"] boolValue];
     pass = pass && [event[@"decoded_local_allocation_word"] unsignedIntValue] == frame * 64 + 1536 && [event[@"decoded_registers"] unsignedIntValue] == config.registers && [event[@"decoded_code_bytes"] unsignedIntValue] == program.length;
     pass = pass && [event[@"launch_words_9_11"] isEqual:@[@(frame * 64), @576]];
    }
    pass = pass && imports > 0;
   }
   [runs addObject:@{@"function":name, @"case":@(kind), @"expected_rejection":@(expectedRejection), @"pipeline_created":@(pipeline != nil), @"PASS":@(pass), @"constructor_restored":@(restored), @"error":error.localizedDescription ?: @"", @"import":proof ?: @{}, @"GPU_command_buffers":@0}];
   all = all && pass;
  }}
 }
 NSDictionary *result = @{@"status":all ? @"PASS" : @"FAIL", @"mode":mode, @"device":device.name, @"registry_id":@(device.registryID), @"runs":runs, @"constructor_restored":@(method_getImplementation(method) == original), @"GPU_command_buffers":@0, @"GPU_dispatches":@0, @"system_modified":@NO, @"performance_benchmark":@NO};
 NSData *json = [NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];
 fwrite(json.bytes, 1, json.length, stdout); puts(""); return all ? 0 : 3;
}}
