#include <thread>
// No producer or consumer dispatch is encoded in these rejection cases.
static NSArray*runPublicArgumentRefusals(id<MTLDevice>d,KPCPUICBScope*scope,id<MTLIndirectCommandBuffer>icb,NSArray*entries,NSDictionary*buffers,NSArray*params,NSArray*pipelines,id<MTLComputePipelineState>writer,unsigned trial){
 NSMutableArray*rows=[NSMutableArray new];
 NSArray*cases=@[@"bad_descriptor_count",@"duplicate_descriptor",@"descriptor_array",@"descriptor_type",@"unprepared_ICB",@"foreign_ICB",@"Private_root",@"unaligned_root",@"short_root",@"root_alias_parameters",@"root_alias_target_parameters",@"overlapping_roots",@"foreign_pipeline",@"unknown_buffer",@"wrong_parameter_offset",@"missing_counter",@"mixed_catalogue",@"caller_tampered_root",@"unsupported_texture",@"array_range",@"wrong_thread"];
 for(NSString*test in cases){
  __weak id weakPlan=nil,weakEncoder=nil;BOOL accepted=NO,validationFailed=NO;NSString*reason=@"";BOOL paramsIntact=NO;
  @autoreleasepool{
   NSError*error=nil;KPGPUCommandSelection*p=[scope newGPUCommandIRv2FromBuffer:icb sourceRange:NSMakeRange(0,3)destination:icb destinationRange:NSMakeRange(3,3)resources:entries records:buffers[@"records"]recordOffset:128 error:&error];
   if(!p)return nil;weakPlan=p;
   id<MTLBuffer>root=[d newBufferWithLength:272 options:MTLResourceStorageModeShared];memset(root.contents,0xa5,root.length);id<MTLBuffer>param=params[[test isEqual:@"root_alias_target_parameters"]?3:0];NSData*before=[NSData dataWithBytes:param.contents length:param.length];
   BOOL validatorCase=[@[@"unknown_buffer",@"wrong_parameter_offset",@"missing_counter",@"mixed_catalogue",@"caller_tampered_root"]containsObject:test];
   @try{
    id<MTLArgumentEncoder>e=nil;
    if([test hasPrefix:@"bad_descriptor"]||[test hasPrefix:@"descriptor_"]||[test isEqual:@"duplicate_descriptor"]){
     NSMutableArray*a=[NSMutableArray new];for(unsigned i=0;i<6;i++){MTLArgumentDescriptor*x=[MTLArgumentDescriptor argumentDescriptor];x.index=i;x.arrayLength=1;x.dataType=i==0?MTLDataTypeIndirectCommandBuffer:i==1?MTLDataTypeComputePipeline:MTLDataTypePointer;[a addObject:x];}
     if([test isEqual:@"bad_descriptor_count"])[a removeLastObject];
     if([test isEqual:@"bad_descriptor_count"])[a removeLastObject];
     if([test isEqual:@"duplicate_descriptor"])((MTLArgumentDescriptor*)a[2]).index=1;
     if([test isEqual:@"descriptor_array"])((MTLArgumentDescriptor*)a[2]).arrayLength=2;
     if([test isEqual:@"descriptor_type"])((MTLArgumentDescriptor*)a[2]).dataType=MTLDataTypeTexture;
     e=[d newArgumentEncoderWithArguments:a];
    }else{
     e=publicArgumentEncoder(d);weakEncoder=e;
     if([test isEqual:@"Private_root"]){[e setArgumentBuffer:[d newBufferWithLength:272 options:MTLResourceStorageModePrivate]offset:64];}
     else if([test isEqual:@"unaligned_root"]){[e setArgumentBuffer:root offset:65];}
     else if([test isEqual:@"short_root"]){[e setArgumentBuffer:[d newBufferWithLength:16 options:MTLResourceStorageModeShared]offset:0];}
     else if([test isEqual:@"root_alias_parameters"]||[test isEqual:@"root_alias_target_parameters"]){[e setArgumentBuffer:param offset:256];[e setIndirectCommandBuffer:icb atIndex:0];}
     else if([test isEqual:@"foreign_ICB"]){[e setArgumentBuffer:root offset:64];[e setIndirectCommandBuffer:(id)[NSObject new]atIndex:0];}
     else if([test isEqual:@"unprepared_ICB"]){MTLIndirectCommandBufferDescriptor*x=[MTLIndirectCommandBufferDescriptor new];x.commandTypes=MTLIndirectCommandTypeConcurrentDispatch;x.inheritBuffers=NO;x.inheritPipelineState=NO;x.maxKernelBufferBindCount=4;id unprepared=[d newIndirectCommandBufferWithDescriptor:x maxCommandCount:3 options:MTLResourceStorageModeShared];[e setArgumentBuffer:root offset:64];[e setIndirectCommandBuffer:unprepared atIndex:0];}
     else if([test isEqual:@"wrong_thread"]){BOOL rejected=NO;std::thread t([&]{@autoreleasepool{@try{[e setArgumentBuffer:root offset:64];[e setIndirectCommandBuffer:icb atIndex:0];}@catch(NSException*x){rejected=[x.name isEqual:@"KeplerCPUICBUnsupported"];}}});t.join();if(rejected)@throw[NSException exceptionWithName:@"KeplerCPUICBUnsupported" reason:@"Creating-thread confinement enforced" userInfo:nil];}
     else{
      [e setArgumentBuffer:root offset:64];[e setIndirectCommandBuffer:icb atIndex:0];[e setComputePipelineState:pipelines[0]atIndex:1];[e setBuffer:buffers[@"stage0"]offset:128 atIndex:2];[e setBuffer:buffers[@"input"]offset:128 atIndex:3];[e setBuffer:params[0]offset:256 atIndex:4];[e setBuffer:buffers[@"counter"]offset:128 atIndex:5];
      if(![p validateCommandIRArgumentBindings:&error])return nil;
      if([test isEqual:@"foreign_pipeline"])[e setComputePipelineState:writer atIndex:1];
      else if([test isEqual:@"overlapping_roots"]){id<MTLArgumentEncoder>other=publicArgumentEncoder(d);[other setArgumentBuffer:root offset:72];[other setIndirectCommandBuffer:icb atIndex:0];}
      else if([test isEqual:@"unknown_buffer"])[e setBuffer:buffers[@"dummy0"]offset:128 atIndex:2];
      else if([test isEqual:@"wrong_parameter_offset"])[e setBuffer:params[0]offset:272 atIndex:4];
      else if([test isEqual:@"missing_counter"])[e setBuffer:nil offset:0 atIndex:5];
      else if([test isEqual:@"mixed_catalogue"])[e setBuffer:buffers[@"stage1"]offset:128 atIndex:3];
      else if([test isEqual:@"caller_tampered_root"])((unsigned char*)root.contents)[72]^=0x80;
      else if([test isEqual:@"unsupported_texture"])[e setTexture:nil atIndex:2];
      else if([test isEqual:@"array_range"]){id<MTLBuffer> __unsafe_unretained b[1]={buffers[@"input"]};NSUInteger offsets[1]={128};[e setBuffers:b offsets:offsets withRange:NSMakeRange(2,5)];}
     }
     if(validatorCase){NSError*failure=nil;validationFailed=![p validateCommandIRArgumentBindings:&failure]&&failure!=nil;accepted=validationFailed;reason=failure.localizedDescription?:@"";}
    }
   }@catch(NSException*x){accepted=!validatorCase&&[x.name isEqual:@"KeplerCPUICBUnsupported"];reason=x.reason?:@"";}
   paramsIntact=before.length==param.length&&!memcmp(before.bytes,param.contents,before.length);
  }
  [rows addObject:@{@"case":test,@"PASS":@(accepted&&paramsIntact&&!weakPlan&&!weakEncoder),@"reason":reason,@"validator_refusal":@(validationFailed),@"parameters_unchanged":@(paramsIntact),@"plan_released":@(weakPlan==nil),@"encoder_released":@(weakEncoder==nil),@"user_kernel_submitted":@NO}];
 }
 return rows;
}
