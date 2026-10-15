#import "KeplerProgramImport.h"
extern "C" unsigned KPReturnCreated();
extern "C" unsigned KPReturnDestroyed();
int main(){@autoreleasepool{
 NSMutableArray*rows=[NSMutableArray new];KeplerImportConfig config={24,576,576};
 for(NSString*name in @[@"compute",@"fragment",@"vertex",@"tessellation",@"graphics",@"host_buffer"]){
  __weak id observed=nil;
  @autoreleasepool{
   id object=nil;
   if([name isEqual:@"compute"])object=KPCreatePipeline(nil,nil,nil,nil,config,nil,nil);
   else if([name isEqual:@"fragment"])object=KPCreateRenderPipeline(nil,nil,nil,config,nil,nil);
   else if([name isEqual:@"vertex"])object=KPCreateVertexPipeline(nil,nil,nil,config,nil,nil);
   else if([name isEqual:@"tessellation"])object=KPCreateTessellationPipeline(nil,nil,nil,config,nil,nil);
   else if([name isEqual:@"graphics"])object=KPCreateGraphicsPipeline(nil,nil,nil,config,nil,config,nil,nil);
   else object=KPCreateHostBuffer(nil,nullptr,128,false);
   if(!object)return 2;observed=object;
  }
  [rows addObject:@{@"factory":name,@"alive_after_ARC_pool":@(observed!=nil),@"created":@(KPReturnCreated()),@"destroyed":@(KPReturnDestroyed())}];
 }
 NSData*d=[NSJSONSerialization dataWithJSONObject:@{@"CPU_only":@YES,@"Metal_device_created":@NO,@"created":@(KPReturnCreated()),@"destroyed":@(KPReturnDestroyed()),@"rows":rows}options:NSJSONWritingPrettyPrinted error:nil];fwrite(d.bytes,1,d.length,stdout);puts("");return 0;
}}
