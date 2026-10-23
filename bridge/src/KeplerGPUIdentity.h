// SPDX-License-Identifier: MIT
#pragma once
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <IOKit/IOKitLib.h>
#include <dlfcn.h>

// A registry entry ID identifies this boot's object, not a hardware model.
// Use only public, read-only IOKit calls to resolve its PCI ancestor. Resolve
// the system framework lazily so existing static-library clients need no new
// linker flag. The framework handle intentionally lives for the process.
static inline NSDictionary *KPKepler880MIdentity(id<MTLDevice> device) {
 if(!device||![device.name isEqual:@"NVIDIA GeForce GTX 880M"]||!device.registryID)return nil;
 struct API {
  void *handle=dlopen("/System/Library/Frameworks/IOKit.framework/IOKit",RTLD_LAZY|RTLD_LOCAL);
  decltype(&IORegistryEntryIDMatching) matching=(decltype(matching))dlsym(handle,"IORegistryEntryIDMatching");
  decltype(&IOServiceGetMatchingService) service=(decltype(service))dlsym(handle,"IOServiceGetMatchingService");
  decltype(&IORegistryEntryGetRegistryEntryID) identity=(decltype(identity))dlsym(handle,"IORegistryEntryGetRegistryEntryID");
  decltype(&IORegistryEntryGetParentEntry) parent=(decltype(parent))dlsym(handle,"IORegistryEntryGetParentEntry");
  decltype(&IORegistryEntryCreateCFProperty) property=(decltype(property))dlsym(handle,"IORegistryEntryCreateCFProperty");
  decltype(&IOObjectConformsTo) conforms=(decltype(conforms))dlsym(handle,"IOObjectConformsTo");
  decltype(&IOObjectRelease) release=(decltype(release))dlsym(handle,"IOObjectRelease");
 };
 static const API f;
 if(!f.handle||!f.matching||!f.service||!f.identity||!f.parent||!f.property||!f.conforms||!f.release)return nil;
 CFMutableDictionaryRef match=f.matching(device.registryID);if(!match)return nil;
 io_registry_entry_t node=f.service(0,match);if(!node)return nil; // consumes match
 uint64_t entryID=0;
 if(f.identity(node,&entryID)!=KERN_SUCCESS||entryID!=device.registryID){f.release(node);return nil;}
 for(unsigned depth=0;depth<16;depth++) {
  if(f.conforms(node,"IOPCIDevice")) {
   uint64_t pciID=0;bool hasID=f.identity(node,&pciID)==KERN_SUCCESS;
   auto number=[&](CFStringRef key)->uint32_t{
    CFTypeRef value=f.property(node,key,kCFAllocatorDefault,0);uint32_t result=0;
    if(value&&CFGetTypeID(value)==CFDataGetTypeID()&&CFDataGetLength((CFDataRef)value)==4){
     const UInt8*p=CFDataGetBytePtr((CFDataRef)value);result=p[0]|uint32_t(p[1])<<8|uint32_t(p[2])<<16|uint32_t(p[3])<<24;
    }
    if(value)CFRelease(value);return result;
   };
   uint32_t vendor=number(CFSTR("vendor-id")),model=number(CFSTR("device-id"));f.release(node);
   if(!hasID||vendor!=0x10de||model!=0x1198)return nil;
   return @{@"schema":@1,@"name":device.name,@"registry_id":@(device.registryID),
    @"PCI_registry_id":@(pciID),@"PCI_vendor_id":@(vendor),@"PCI_device_id":@(model)};
  }
  io_registry_entry_t next=0;kern_return_t status=f.parent(node,"IOService",&next);f.release(node);
  if(status!=KERN_SUCCESS||!next)return nil;node=next;
 }
 f.release(node);return nil;
}
