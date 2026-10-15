#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <thread>
#include <mutex>
#include <condition_variable>
#include <atomic>
#include <chrono>
#include <cstring>
int main(){@autoreleasepool{
 id<MTLDevice>d=nil;for(id<MTLDevice>x in MTLCopyAllDevices())if(x.registryID==4294968458)d=x;if(!d)return 2;
 id<MTLCommandQueue>q=[d newCommandQueue];id<MTLSharedEvent>gate=[d newSharedEvent];if(!gate)return 3;gate.signaledValue=0;
 uint32_t value=0x723456abu,zero=0;id<MTLBuffer>input=[d newBufferWithBytes:&value length:4 options:MTLResourceStorageModeShared],output=[d newBufferWithBytes:&zero length:4 options:MTLResourceStorageModeShared];if(!input||!output)return 3;
 std::mutex mutex;std::condition_variable wake;bool released=false;std::atomic<bool>watchdogFired(false);
  std::thread watchdog([&]{@autoreleasepool{std::unique_lock<std::mutex>lock(mutex);if(!wake.wait_for(lock,std::chrono::seconds(2),[&]{return released;})){watchdogFired.store(true);gate.signaledValue=1;}}});
 id<MTLCommandBuffer>c=[q commandBuffer];NSUInteger status=99;uint32_t before=99;
 @try{[c encodeWaitForEvent:gate value:1];id<MTLBlitCommandEncoder>b=[c blitCommandEncoder];[b copyFromBuffer:input sourceOffset:0 toBuffer:output destinationOffset:0 size:4];[b endEncoding];[c commit];status=c.status;memcpy(&before,output.contents,4);std::this_thread::sleep_for(std::chrono::milliseconds(2200));}
 @finally{gate.signaledValue=1;{std::lock_guard<std::mutex>lock(mutex);released=true;}wake.notify_all();watchdog.join();}
 [c waitUntilCompleted];uint32_t result=0;memcpy(&result,output.contents,4);BOOL passed=watchdogFired.load()&&before==0&&(status==2||status==3)&&c.status==4&&result==value&&gate.signaledValue==1;
 NSDictionary*r=@{@"device":d.name,@"registry_id":@(d.registryID),@"pending_status":@(status),@"marker_before_guard":@(before),@"marker_final":@(result),@"marker_expected":@(value),@"watchdog_fired":@(watchdogFired.load()),@"gate_final_value":@(gate.signaledValue),@"final_status":@(c.status),@"user_kernel_dispatches":@0,@"status":passed?@"PASS_EXPECTED_WATCHDOG_RELEASE":@"FAIL",@"system_modified":@NO};NSData*j=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];fwrite(j.bytes,1,j.length,stdout);puts("");return passed?0:1;
}}
