// SPDX-License-Identifier: MIT
#import <Foundation/Foundation.h>
#include "video_registry_metadata.h"
#include <atomic>
#include <cstdio>
#include <thread>

int main(){ @autoreleasepool {
    if(KPRegistryMetadataBegin(0,0x202)||KPRegistryMetadataBegin(0x101,0)||KPRegistryMetadataSnapshot()!=nil)return 9;
    for(unsigned round=0;round<3;++round){
        if(!KPRegistryMetadataBegin(0x101,0x202))return 10;
        std::atomic<bool> denied{false}, wrongSnapshot{false};
        std::thread contender([&]{@autoreleasepool {
            denied=!KPRegistryMetadataBegin(0x101,0x202);
            wrongSnapshot=KPRegistryMetadataSnapshot()==nil;
        }});
        contender.join(); if(!denied||!wrongSnapshot)return 11;
        CFMutableDictionaryRef object=CFDictionaryCreateMutable(kCFAllocatorDefault,0,
            &kCFTypeDictionaryKeyCallBacks,&kCFTypeDictionaryValueCallBacks);
        if(!object)return 12;
        CFDictionarySetValue(object,CFSTR("KeplerMetal control"),kCFBooleanTrue);
        KPRegistryMetadataControl(true); CFTypeRef retained=CFRetain(object); KPRegistryMetadataControl(false);
        bool equal=retained==object; CFRelease(retained); CFRelease(object); if(!equal)return 13;
        NSDictionary *snapshot=KPRegistryMetadataSnapshot();
        NSArray *events=snapshot[@"events"];
        if(![snapshot[@"status"]isEqual:@"COMPLETE"]||[snapshot[@"calls"]unsignedIntValue]!=1||
           [snapshot[@"dropped"]unsignedIntValue]||[snapshot[@"pending"]unsignedIntValue]||events.count!=1||
           ![events[0][@"synthetic_control"]boolValue]||![snapshot[@"recorders_drained"]boolValue])return 14;
        if(KPRegistryMetadataSnapshot()!=nil)return 15;
    }
    std::puts("PASS three independent metadata generations and concurrent refusal");return 0;
}}
