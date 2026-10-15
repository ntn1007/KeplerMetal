#include "IOKitKeplerBridge.h"
#include <IOKit/IOKitLib.h>
#include <CoreFoundation/CoreFoundation.h>
#include <cstring>
#include <cstdio>
struct KBContext {
 io_service_t service=IO_OBJECT_NULL;
 io_connect_t clients[3]={0,0,0};
 mach_vm_address_t addresses[2]={0,0};
 mach_vm_size_t sizes[2]={0,0};
 bool mapped[2]={false,false};
};
static uint32_t pci_property(io_service_t s,CFStringRef key){
 CFTypeRef p=IORegistryEntrySearchCFProperty(s,kIOServicePlane,key,kCFAllocatorDefault,kIORegistryIterateParents|kIORegistryIterateRecursively);uint32_t v=0;
 if(p){if(CFGetTypeID(p)==CFDataGetTypeID()&&CFDataGetLength((CFDataRef)p)>=4)memcpy(&v,CFDataGetBytePtr((CFDataRef)p),4);CFRelease(p);}return v;
}
KBContext*kb_open(KBInfo*info){
 if(!info)return nullptr;memset(info,0,sizeof(*info));auto*c=new KBContext();c->service=IOServiceGetMatchingService(kIOMainPortDefault,IOServiceMatching("nvAccelerator"));if(!c->service){delete c;return nullptr;}
 info->pci_vendor=pci_property(c->service,CFSTR("vendor-id"));info->pci_device=pci_property(c->service,CFSTR("device-id"));IORegistryEntryGetRegistryEntryID(c->service,&info->registry_id);
 if(info->pci_vendor!=0x10de||info->pci_device!=0x1198){fprintf(stderr,"Expected GTX 880M 10de:1198, got %04x:%04x\n",info->pci_vendor,info->pci_device);kb_close(c);return nullptr;}
 // These client types and mappings were observed in our successful Metal probe.
 const uint32_t types[3]={5,6,8};for(int i=0;i<3;i++){kern_return_t r=IOServiceOpen(c->service,mach_task_self(),types[i],&c->clients[i]);if(r!=KERN_SUCCESS){fprintf(stderr,"IOServiceOpen type=%u status=%u\n",types[i],(unsigned)r);kb_close(c);return nullptr;}info->opened_client_mask|=1u<<i;}
 const uint32_t memory_types[2]={5,1};for(int i=0;i<2;i++){kern_return_t r=IOConnectMapMemory64(c->clients[i],memory_types[i],mach_task_self(),&c->addresses[i],&c->sizes[i],kIOMapAnywhere);if(r==KERN_SUCCESS)c->mapped[i]=true;else fprintf(stderr,"Map client=%u memory=%u status=%u\n",types[i],memory_types[i],(unsigned)r);}
 info->shared_device_bytes=c->sizes[0];info->shared_resource_bytes=c->sizes[1];info->native_submission_supported=0;return c;
}
int kb_submit_native(KBContext*,const uint32_t*,uint32_t){return KB_NATIVE_SUBMISSION_NOT_IMPLEMENTED;}
void kb_close(KBContext*c){
 if(!c)return;const uint32_t types[2]={5,1};for(int i=0;i<2;i++)if(c->mapped[i])IOConnectUnmapMemory64(c->clients[i],types[i],mach_task_self(),c->addresses[i]);for(auto port:c->clients)if(port)IOServiceClose(port);if(c->service)IOObjectRelease(c->service);delete c;
}
