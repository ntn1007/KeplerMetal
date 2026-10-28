#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Apply one observation-only callsite extension to the pinned dependency source."""
def once(s,old,new):
 if s.count(old)!=1:raise ValueError('Expected dependency source fragment differs')
 return s.replace(old,new)
def apply(s):
 s=once(s,'#include <cstring>','#include <cstring>\n#include <cerrno>')
 s=once(s,'bool control=false,present=false,originalPresent=false,changed=false,truncated=false;', 'bool control=false,present=false,originalPresent=false,changed=false,truncated=false,gva=false;')
 anchor='__attribute__((noinline)) CFTypeRef observedSearch(io_registry_entry_t entry,const io_name_t plane,'
 helper='''// Observe the additional GVA callsite, but never substitute its return.
bool gvaSite(uintptr_t caller){
 Dl_info info{};if(!dladdr((void*)caller,&info)||!info.dli_fname||!strstr(info.dli_fname,"/AppleGVA")||caller-(uintptr_t)info.dli_fbase!=149913)return false;
 uintptr_t base=(uintptr_t)info.dli_fbase;NSData*header=resident(base,sizeof(mach_header_64));if(!header)return false;auto h=(const mach_header_64*)header.bytes;if(h->magic!=MH_MAGIC_64||h->ncmds>4096||h->sizeofcmds>1048576)return false;NSData*cmds=resident(base+sizeof(*h),h->sizeofcmds);if(!cmds)return false;
 const unsigned char expected[]={0xca,0x54,0x14,0xf3,0x69,0x37,0x3c,0x05,0x9e,0xa2,0xd8,0x2b,0x35,0xaf,0xd4,0xf0};bool valid=false;size_t off=0;for(unsigned i=0;i<h->ncmds;i++){if(off+sizeof(load_command)>cmds.length)return false;auto c=(const load_command*)((const uint8_t*)cmds.bytes+off);if(c->cmdsize<sizeof(load_command)||c->cmdsize>cmds.length-off)return false;if(c->cmd==LC_UUID){if(c->cmdsize<sizeof(uuid_command)||valid)return false;valid=!memcmp(((const uuid_command*)c)->uuid,expected,sizeof(expected));}off+=c->cmdsize;}
 bool result=valid&&off==cmds.length&&[digest(resident(base+148746,2669))isEqual:@"f8a1efea62ed7f03028666fe86c35de8f06941324ac8d1ae8815ec93f0eb8a19"];
 if(!result)fprintf(stderr,"KM_GVA_DEP profile_refused\\n");return result;
}
'''
 s=once(s,anchor,helper+anchor)
 old='''    bool candidate=enabled.load(std::memory_order_seq_cst)&&(synthetic||(KPDEP_RECORD&&caller==nativeSite));'''
 new='''    bool gva=false;if(enabled.load(std::memory_order_seq_cst)&&KPDEP_RECORD&&!synthetic&&caller!=nativeSite){int saved=errno;recording=true;@autoreleasepool{gva=gvaSite(caller);}recording=false;errno=saved;}
    bool candidate=enabled.load(std::memory_order_seq_cst)&&(synthetic||(KPDEP_RECORD&&(caller==nativeSite||gva)));'''
 s=once(s,old,new)
 s=once(s,'Event &event=events[index];event.control=synthetic;event.caller=caller;', 'Event &event=events[index];event.control=synthetic;event.gva=gva;event.caller=caller;')
 s=once(s,'@"native_pinned_callsite":@(!e.control&&e.caller==nativeSite)}', '@"native_pinned_callsite":@(!e.control&&e.caller==nativeSite),@"GVA_pinned_callsite":@(!e.control&&e.gva)}')
 return s
