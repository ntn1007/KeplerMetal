#import "KeplerProgramImport.h"
#import <objc/runtime.h>
#include <cstdio>
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=2)return 1;id<MTLDevice>d=MTLCreateSystemDefaultDevice();if(![d.name isEqual:@"NVIDIA GeForce GTX 880M"])return 2;
 Method m=class_getInstanceMethod(objc_getClass("NVMTLFunctionVariant"),sel_registerName("initWithCompilerOutput:size:device:"));if(!m)return 3;IMP before=method_getImplementation(m);
 NSMutableArray*cases=[NSMutableArray array];unsigned char bytes[64]={};NSData*code=[NSData dataWithBytes:bytes length:64];unsigned failures=0;
 for(unsigned i=0;i<5;i++){
  NSError*error=nil;NSDictionary*proof=nil;KeplerImportConfig config={24,576,576};NSData*input=code;
  if(i==0)input=nil;if(i==1)input=[NSData dataWithBytes:bytes length:63];if(i==2)config.registers=64;if(i==3)config.launch_word_9=1;
  id<MTLComputePipelineState>p=KPCreatePipeline(d,[NSURL fileURLWithPath:@(argv[1])],@"not_present",input,config,&error,&proof);
  bool restored=method_getImplementation(m)==before,pass=!p&&restored&&error;
  if(!pass)failures++;[cases addObject:@{@"case":@(i),@"pipeline_rejected":@(p==nil),@"constructor_restored":@(restored),@"error":error.localizedDescription?:@"",@"evidence":proof?:@{},@"pass":@(pass)}];[p release];
 }
 NSDictionary*r=@{@"cases":cases,@"failures":@(failures),@"GPU_dispatch":@NO,@"scope":@"real device and constructor restoration on rejected inputs/missing library; no kernel submission"};NSData*json=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];fwrite(json.bytes,1,json.length,stdout);puts("");return failures?10:0;
}}
