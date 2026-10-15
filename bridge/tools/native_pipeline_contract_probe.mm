// Native public API observations only; no scope/hook or command submission.
#import <Metal/Metal.h>
#import <objc/runtime.h>
#include <cstdio>
#include "KeplerCommandIRReflection.inc"
static NSDictionary*argument(MTLArgument*a){
 NSMutableDictionary*r=[@{@"name":a.name?:@"",@"index":@(a.index),@"type":@(a.type),@"active":@(a.active),@"access":@(a.access)}mutableCopy];
 if(a.type==MTLArgumentTypeBuffer){r[@"size"]=@(a.bufferDataSize);r[@"alignment"]=@(a.bufferAlignment);r[@"data_type"]=@(a.bufferDataType);NSMutableArray*members=[NSMutableArray new];for(MTLStructMember*m in a.bufferStructType.members)[members addObject:@{@"name":m.name?:@"",@"type":@(m.dataType),@"offset":@(m.offset),@"index":@(m.argumentIndex)}];r[@"members"]=members;}
 return r;
}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=4)return 1;NSString*assets=@(argv[1]);id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458)d=x;if(!d)return 2;
 NSMutableArray*runs=[NSMutableArray new];
 for(NSArray*pair in @[@[@"consumer.metallib",@"dependency_seed"],@[@"producer.metallib",@"encode_dataflow_basic"]]){
  NSError*error=nil;id<MTLLibrary>lib=[d newLibraryWithURL:[NSURL fileURLWithPath:[assets stringByAppendingPathComponent:pair[0]]]error:&error];id<MTLFunction>f=[lib newFunctionWithName:pair[1]];if(!f)return 3;
  MTLArgument*root=nil;id<MTLArgumentEncoder>ae=[f newArgumentEncoderWithBufferIndex:0 reflection:&root];NSDictionary*rootInfo=root?argument(root):@{};
  if([pair[1]hasPrefix:@"encode_"]){KPIRComputeReflection*projection=[[KPIRComputeReflection alloc]initWithNativeArgument:root];if(!projection||projection.arguments.count!=1||projection.arguments[0]!=root||projection.bindings.count!=1||![projection.bindings[0]conformsToProtocol:@protocol(MTLBufferBinding)])return 4;id<MTLBufferBinding>b=(id)projection.bindings[0];if(b.bufferStructType!=root.bufferStructType||b.bufferDataSize!=48||b.index!=0||b.type!=MTLBindingTypeBuffer)return 4;}

  for(unsigned kind=0;kind<2;kind++)for(unsigned options=0;options<4;options++){
   MTLComputePipelineReflection*reflection=nil;id<MTLComputePipelineState>pipeline=nil;error=nil;NSString*exception=nil;
   @try{if(kind){MTLComputePipelineDescriptor*p=[MTLComputePipelineDescriptor new];p.computeFunction=f;p.label=@"native-contract";pipeline=[d newComputePipelineStateWithDescriptor:p options:options reflection:&reflection error:&error];}
   else pipeline=[d newComputePipelineStateWithFunction:f options:options reflection:&reflection error:&error];}
   @catch(NSException*x){exception=x.reason?:x.name;}
   NSMutableArray*arguments=[NSMutableArray new];for(MTLArgument*a in reflection.arguments)[arguments addObject:argument(a)];NSMutableArray*bindings=[NSMutableArray new];NSString*bindingException=nil;
   @try{if([reflection respondsToSelector:@selector(bindings)])for(id<MTLBinding>b in reflection.bindings)[bindings addObject:@{@"name":b.name?:@"",@"index":@(b.index),@"type":@(b.type),@"access":@(b.access),@"class":NSStringFromClass(object_getClass(b))}];}@catch(NSException*x){bindingException=x.reason?:x.name;}
   [runs addObject:@{@"function":pair[1],@"factory":kind?@"descriptor":@"function-options",@"options":@(options),@"pipeline":@(pipeline!=nil),@"error":error.description?:@"",@"exception":exception?:@"",@"reflection":@(reflection!=nil),@"reflection_class":reflection?NSStringFromClass(object_getClass(reflection)):@"",@"arguments":arguments,@"bindings":bindings,@"bindings_exception":bindingException?:@"",@"function_root":rootInfo,@"function_encoder_bytes":@(ae.encodedLength),@"GPU_dispatch":@NO}];
  }
 }
 NSDictionary*v=@{@"device":d.name,@"registry_id":@(d.registryID),@"runs":runs,@"command_buffers_submitted":@NO,@"system_modified":@NO};NSData*j=[NSJSONSerialization dataWithJSONObject:v options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return 0;
}}
