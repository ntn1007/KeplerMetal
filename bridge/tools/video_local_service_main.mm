// SPDX-License-Identifier: MIT
#import <Foundation/Foundation.h>
#include <atomic>
#include <thread>
#include <chrono>
#include <unistd.h>
extern "C" bool KPVideoOwnedBegin(NSString *,NSString *);
extern "C" NSDictionary *KPVideoOwnedSnapshot();
int KPRegistryQualifiedMain(int,char **);
int main(int argc,char **argv){@autoreleasepool{
    if(argc!=4||![@[@"inspect",@"cpu",@"hardware"]containsObject:@(argv[3])])return 1;
    std::atomic<bool> done{false};
    std::thread watchdog([&]{
        for(unsigned i=0;i<1200;i++){if(done.load())return;std::this_thread::sleep_for(std::chrono::milliseconds(10));}
        const char message[]="{\"status\":\"OWNED_NATIVE_VIDEO_TIMEOUT\",\"hardware_video_execution_proved\":false}\n";
        write(STDERR_FILENO,message,sizeof(message)-1);_exit(6);
    });
    if(!KPVideoOwnedBegin(@(argv[1]),@(argv[3]))){done=true;watchdog.join();return 2;}
    int status=KPRegistryQualifiedMain(argc,argv);
    NSDictionary *result=KPVideoOwnedSnapshot();
    NSData *data=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];
    bool written=[data writeToFile:[@(argv[2])stringByAppendingPathComponent:@"owned.json"]options:0 error:nil];
    done=true;watchdog.join();
    return status?status:(!written?3:([result[@"status"]isEqual:@"COMPLETE"]?0:4));
}}
