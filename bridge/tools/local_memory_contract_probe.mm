// SPDX-License-Identifier: MIT
// Negative allocation/profile contracts; creates no command buffers.
#import "KeplerProgramImport.h"
#import <objc/runtime.h>
#include <cstdio>
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=4)return 1;NSString*assets=@(argv[1]);id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458)d=x;if(!d)return 2;
 NSData*source=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"local_memory.metallib"]],*program=[NSData dataWithContentsOfFile:[assets stringByAppendingPathComponent:@"local32.sass"]];
 Method constructor=class_getInstanceMethod(objc_getClass("NVMTLFunctionVariant"),sel_registerName("initWithCompilerOutput:size:device:"));if(!constructor)return 3;IMP before=method_getImplementation(constructor);NSMutableArray*runs=[NSMutableArray new];
 for(unsigned kind=0;kind<13;kind++){
  NSMutableData*library=[source mutableCopy],*code=[program mutableCopy];NSData*libArg=library,*codeArg=code;id<MTLDevice>device=d;NSString*function=@"local32";KeplerLocalMemoryConfig config={24,128,128,0,0};
  switch(kind){
   case 0:((uint8_t*)library.mutableBytes)[0]^=1;break;
   case 1:config.required_scratch_bytes=132;break;
   case 2:config.carrier_local_bytes=256;break;
   case 3:config.carrier_spill_bytes=4;break;
   case 4:config.carrier_control_barriers=1;break;
   case 5:config.registers=23;break;
   case 6:config.registers=64;break;
   case 7:function=@"not_a_qualified_carrier";break;
   case 8:[code setLength:code.length-1];break;
   case 9:libArg=nil;break;
   case 10:codeArg=nil;break;
   case 11:device=nil;break; // Exercises cleanup after the opt-in TLS is armed.
   case 12:[code setLength:0];break;
  }
  NSError*error=nil;NSDictionary*proof=nil;id<MTLComputePipelineState>pipeline=KPCreateLocalMemoryPipeline(device,libArg,function,codeArg,config,&error,&proof);
  BOOL restored=method_getImplementation(constructor)==before,ok=!pipeline&&error&&restored;
  [runs addObject:@{@"kind":@"rejected_contract",@"case":@(kind),@"PASS":@(ok),@"pipeline_created":@(pipeline!=nil),@"error":error.description?:@"",@"constructor_restored":@(restored),@"GPU_command_buffers":@0}];if(!ok)return 4;
 }
 NSError*error=nil;NSDictionary*proof=nil;id<MTLComputePipelineState>pipeline=KPCreateLocalMemoryPipeline(d,source,@"local32",program,{24,128,128,0,0},&error,&proof);
 BOOL ok=pipeline&&!error&&[proof[@"contract_verified"]boolValue]&&! [proof[@"rejected_import"]boolValue]&&method_getImplementation(constructor)==before;
 [runs addObject:@{@"kind":@"valid_after_rejections",@"PASS":@(ok),@"constructor_restored":@(method_getImplementation(constructor)==before),@"import":proof?:@{},@"GPU_command_buffers":@0}];
 NSDictionary*r=@{@"device":d.name,@"runs":runs,@"legacy_config_bytes":@(sizeof(KeplerImportConfig)),@"GPU_command_buffers":@0,@"system_modified":@NO};NSData*j=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return ok?0:5;
}}
