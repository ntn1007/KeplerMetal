#import "KeplerProgramImport.h"
#include <cstring>
#include <vector>
#include <unistd.h>

static NSUInteger alive(NSPointerArray *objects) {
 NSUInteger n=0;
 for(NSUInteger i=0;i<objects.count;i++) if([objects pointerAtIndex:i]) n++;
 return n;
}
static void idle(NSPointerArray *objects) {
 for(unsigned i=0;i<250&&alive(objects);i++) {
  @autoreleasepool { usleep(1000); }
 }
}
int main(int argc,char **argv) { @autoreleasepool {
 if(argc!=4)return 1;
 NSArray *parts=[@(argv[3]) componentsSeparatedByString:@":"];
 if(parts.count!=2)return 1;
 NSString *provider=parts[0],*policy=parts[1];
 if(![@[@"native",@"factory"] containsObject:provider] || ![@[@"clean",@"dirty",@"cancel",@"bytes",@"bytes_cancel"] containsObject:policy])return 1;
 BOOL factory=[provider isEqual:@"factory"],dirty=[@[@"dirty",@"cancel"]containsObject:policy],cancel=[policy isEqual:@"cancel"]||[policy isEqual:@"bytes_cancel"],bytes=[policy hasPrefix:@"bytes"];
 if(factory&&bytes)return 1;
 id<MTLDevice>d=nil;
 for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458)d=x;
 if(!d)return 2;
 NSMutableArray *runs=[NSMutableArray new];
 unsigned counts[4]={257,1025,4096,8191};
 for(unsigned trial=0;trial<4;trial++) {
  NSPointerArray *observed=[NSPointerArray weakObjectsPointerArray];
  __weak id weakAbandoned=nil;
  NSMutableDictionary *row=[@{@"trial":@(trial),@"dirty_notification":@(dirty),@"original_command_created":@(cancel),@"original_committed":@NO}mutableCopy];
  @autoreleasepool {
   NSUInteger sizes[3]={counts[trial]*16+128,counts[trial]*16+128,48};
   NSMutableArray *buffers=[NSMutableArray new];
   for(unsigned k=0;k<3;k++) {
    std::vector<unsigned char> initial(sizes[k],0xa5);
    id<MTLBuffer>b=nil;
    if(factory)b=KPCreateHostBuffer(d,dirty?initial.data():nullptr,sizes[k],false);
    else if(bytes)b=[d newBufferWithBytes:initial.data() length:sizes[k] options:MTLResourceStorageModeManaged];
    else {
     b=[d newBufferWithLength:sizes[k] options:MTLResourceStorageModeManaged];
     if(b&&dirty){memcpy(b.contents,initial.data(),sizes[k]);[b didModifyRange:NSMakeRange(0,sizes[k])];}
    }
    if(!b||b.storageMode!=MTLStorageModeManaged)return 3;
    [buffers addObject:b];[observed addPointer:(__bridge void*)b];
   }
   if(cancel) {
    id<MTLCommandQueue>q=[d newCommandQueue];id<MTLCommandBuffer>cb=[q commandBuffer];weakAbandoned=cb;
    id<MTLBlitCommandEncoder>e=[cb blitCommandEncoder];
    for(id<MTLBuffer>b in buffers) {
     id<MTLBuffer>output=[d newBufferWithLength:b.length options:MTLResourceStorageModeShared];
     if(!output)return 4;
     [e copyFromBuffer:b sourceOffset:0 toBuffer:output destinationOffset:0 size:b.length];
    }
    [e endEncoding];row[@"original_status"]=@(cb.status);
   }
  }
  row[@"alive_after_pool"]=@(alive(observed));row[@"abandoned_object_alive"]=@(weakAbandoned!=nil);
  idle(observed);row[@"alive_after_idle"]=@(alive(observed));
  @autoreleasepool {
   id<MTLCommandQueue>q=[d newCommandQueue];id<MTLCommandBuffer>cb=[q commandBuffer];
   [cb commit];[cb waitUntilCompleted];row[@"unrelated_empty_command_status"]=@(cb.status);
   if(cb.status!=MTLCommandBufferStatusCompleted)return 5;
  }
  idle(observed);row[@"alive_after_unrelated_submission"]=@(alive(observed));
  [runs addObject:row];
 }
 NSDictionary *result=@{@"device":d.name,@"registry_id":@(d.registryID),@"mode":@(argv[3]),@"runs":runs,@"provider":provider,@"policy":policy,@"original_commands_submitted":@NO,@"unrelated_empty_commands_submitted":@YES,@"private_calls":@NO,@"system_modified":@NO,@"performance_benchmark":@NO};
 NSData *json=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];
 fwrite(json.bytes,1,json.length,stdout);puts("");return 0;
}}
