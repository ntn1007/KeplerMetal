#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
int main(){@autoreleasepool{
 id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458)d=x;if(!d)return 2;
 id<MTLCommandQueue>q=[d newCommandQueue];id<MTLCommandBuffer>c=[q commandBuffer];NSUInteger initial=c.status;
 [c enqueue];NSUInteger enqueued=c.status;
 // Always drain the reserved position, including when the observation differs.
 [c commit];[c waitUntilCompleted];
 NSDictionary*r=@{@"device":d.name,@"registry_id":@(d.registryID),@"initial_status":@(initial),@"enqueued_status":@(enqueued),@"final_status":@(c.status),@"retained_references":@(c.retainedReferences),@"user_kernel_dispatches":@0,@"reserved_queue_position_drained":@(c.status==MTLCommandBufferStatusCompleted),@"system_modified":@NO};
 NSData*j=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");
 return initial==MTLCommandBufferStatusNotEnqueued&&enqueued==MTLCommandBufferStatusEnqueued&&c.status==MTLCommandBufferStatusCompleted?0:1;
}}
