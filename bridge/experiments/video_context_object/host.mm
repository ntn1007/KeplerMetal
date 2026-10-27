// SPDX-License-Identifier: MIT
// Public Metal client; the observer only inspects naturally created objects.
#import <Foundation/Foundation.h>
#import <Metal/Metal.h>
#include <IOKit/IOKitLib.h>
#include <unistd.h>
#include <cerrno>
#include <cstring>
#include <cstdlib>
extern "C" void KMObserveBegin(uint64_t,bool,bool);
extern "C" void KMObserveEnd();
extern "C" NSDictionary *KMObserveResults();
static uint32_t value(io_registry_entry_t e,CFStringRef k){CFTypeRef x=IORegistryEntryCreateCFProperty(e,k,kCFAllocatorDefault,0);uint32_t n=0;if(x&&CFGetTypeID(x)==CFDataGetTypeID()&&CFDataGetLength((CFDataRef)x)==4){const UInt8*p=CFDataGetBytePtr((CFDataRef)x);n=p[0]|uint32_t(p[1])<<8|uint32_t(p[2])<<16|uint32_t(p[3])<<24;}if(x)CFRelease(x);return n;}
static bool ancestor(io_registry_entry_t e,uint64_t *id){if(!e||IOObjectRetain(e)!=KERN_SUCCESS)return false;io_registry_entry_t cur=e;bool found=false;for(unsigned k=0;k<32&&cur;k++){if(IOObjectConformsTo(cur,"IOPCIDevice")){uint64_t rid=0;found=value(cur,CFSTR("vendor-id"))==0x10de&&value(cur,CFSTR("device-id"))==0x1198&&IORegistryEntryGetRegistryEntryID(cur,&rid)==KERN_SUCCESS&&rid;if(found)*id=rid;break;}io_registry_entry_t p=0;kern_return_t st=IORegistryEntryGetParentEntry(cur,kIOServicePlane,&p);IOObjectRelease(cur);cur=0;if(st!=KERN_SUCCESS)break;cur=p;}if(cur)IOObjectRelease(cur);return found;}
int main(int argc,char**argv){@autoreleasepool{
 if(argc!=3||(strcmp(argv[1],"observe")&&strcmp(argv[1],"config")&&strcmp(argv[1],"context"))||!argv[2][0]||strspn(argv[2],"0123456789")!=strlen(argv[2]))return 2;char*end=nullptr;errno=0;uint64_t rid=strtoull(argv[2],&end,10);if(errno||!rid||!end||*end)return 2;
 io_service_t service=IOServiceGetMatchingService(kIOMainPortDefault,IORegistryEntryIDMatching(rid));uint64_t pci=0;bool valid=service&&IOObjectConformsTo(service,"nvAccelerator")&&ancestor(service,&pci);if(service)IOObjectRelease(service);if(!valid)return 3;
 bool withConfig=!strcmp(argv[1],"config")||!strcmp(argv[1],"context");bool withContext=!strcmp(argv[1],"context");KMObserveBegin(rid,withConfig,withContext);NSArray<id<MTLDevice>>*all=MTLCopyAllDevices();id<MTLDevice>selected=nil;unsigned hits=0;
 for(id<MTLDevice>d in all){io_service_t s=IOServiceGetMatchingService(kIOMainPortDefault,IORegistryEntryIDMatching(d.registryID));uint64_t id=0;bool same=s&&ancestor(s,&id)&&id==pci;if(s)IOObjectRelease(s);if(same){selected=d;hits++;}}
 id<MTLBuffer>buf=hits==1?[selected newBufferWithLength:4096 options:MTLResourceStorageModeShared]:nil;bool ok=buf&&buf.contents&&buf.length==4096;
 if(ok){uint8_t*p=(uint8_t*)buf.contents;for(unsigned i=0;i<4096;i++)p[i]=(i*13+7)&255;for(unsigned i=0;i<4096;i++)if(p[i]!=((i*13+7)&255))ok=false;}
 KMObserveEnd();NSDictionary*r=@{@"mode":@(argv[1]),@"status":ok?@"OBSERVATION_COMPLETED":@"METAL_FAILED",@"pid":@(getpid()),@"registry_id":@(rid),@"pci_id":@(pci),@"metal_candidates":@(hits),@"buffer_CPU_correct":@(ok),@"observation":KMObserveResults(),@"explicit_GPU_dispatches":@0,@"hardware_video_execution_proved":@NO};NSData*j=[NSJSONSerialization dataWithJSONObject:r options:NSJSONWritingPrettyPrinted error:nil];if(!j)return 4;fwrite(j.bytes,1,j.length,stdout);puts("");return ok?0:5;
}}
