// SPDX-License-Identifier: MIT
#import <Foundation/Foundation.h>
#include <IOKit/IOKitLib.h>
#include <atomic>
#include <cstdio>
#include <thread>
extern "C" bool KPDependencyTestBegin();
extern "C" CFTypeRef KPDependencyTestObserve(io_registry_entry_t,CFStringRef);
extern "C" NSDictionary *KPDependencyTestSnapshot();

int main(){ @autoreleasepool {
    if(KPDependencyTestSnapshot()!=nil)return 1;
    io_registry_entry_t root=IORegistryGetRootEntry(kIOMainPortDefault);if(!root)return 2;
    for(unsigned round=0;round<3;round++){
        if(!KPDependencyTestBegin())return 3;
        std::atomic<bool> denied{false},wrongSnapshot{false};
        std::thread other([&]{@autoreleasepool {
            denied=!KPDependencyTestBegin();wrongSnapshot=KPDependencyTestSnapshot()==nil;
        }});other.join();if(!denied||!wrongSnapshot)return 4;
        CFStringRef key=round==1?CFSTR("KeplerMetal-absent-property-control"):CFSTR("IOKitBuildVersion");
        CFTypeRef expected=IORegistryEntrySearchCFProperty(root,kIOServicePlane,key,kCFAllocatorDefault,0);
        CFTypeRef got=KPDependencyTestObserve(root,key);
        bool correct=(!expected&&!got)||(expected&&got&&CFEqual(expected,got));
        if(expected)CFRelease(expected);if(got)CFRelease(got);if(!correct)return 5;
        NSDictionary *snap=KPDependencyTestSnapshot();NSArray *events=snap[@"events"];
        if(![snap[@"status"]isEqual:@"COMPLETE"]||[snap[@"calls"]unsignedIntValue]!=1||events.count!=1||
           [snap[@"dropped"]unsignedIntValue]||[snap[@"pending"]unsignedIntValue]||
           ![snap[@"recorders_drained"]boolValue]||![events[0][@"synthetic_control"]boolValue]||
           ![events[0][@"key"]isEqual:(id)key]||[events[0][@"return_value_changed"]boolValue])return 6;
        if(KPDependencyTestSnapshot()!=nil)return 7;
    }
    IOObjectRelease(root);std::puts("PASS three independent dependency generations and concurrent refusal");return 0;
}}
