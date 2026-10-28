// SPDX-License-Identifier: MIT
// Own-process, public CFData observer. No private function is invoked.
#import <CoreFoundation/CoreFoundation.h>
#include <CommonCrypto/CommonDigest.h>
#include <mach-o/loader.h>
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <dlfcn.h>
#include <execinfo.h>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <unistd.h>
static thread_local bool active=false;
static bool readable(uintptr_t p,size_t n){mach_vm_address_t start=p;mach_vm_size_t size=0;vm_region_basic_info_data_64_t info{};mach_msg_type_number_t count=VM_REGION_BASIC_INFO_COUNT_64;mach_port_t object=MACH_PORT_NULL;auto r=mach_vm_region(mach_task_self(),&start,&size,VM_REGION_BASIC_INFO_64,(vm_region_info_t)&info,&count,&object);if(object)mach_port_deallocate(mach_task_self(),object);return !r&&(info.protection&VM_PROT_READ)&&p>=start&&n<=size&&p-start<=size-n;}
static bool hashMatches(uintptr_t p,size_t n,const char*expected){if(!readable(p,n))return false;unsigned char bytes[CC_SHA256_DIGEST_LENGTH];CC_SHA256((const void*)p,(CC_LONG)n,bytes);char hex[65];for(unsigned i=0;i<sizeof(bytes);i++)snprintf(hex+i*2,3,"%02x",bytes[i]);return !strcmp(hex,expected);}
static bool validImage(uintptr_t base){
 if(!readable(base,sizeof(mach_header_64)))return false;auto h=(const mach_header_64*)base;if(h->magic!=MH_MAGIC_64||h->ncmds>4096||h->sizeofcmds>1048576||!readable(base+sizeof(*h),h->sizeofcmds))return false;
 const unsigned char expected[]={0xca,0x54,0x14,0xf3,0x69,0x37,0x3c,0x05,0x9e,0xa2,0xd8,0x2b,0x35,0xaf,0xd4,0xf0};bool found=false;uintptr_t p=base+sizeof(*h),end=p+h->sizeofcmds;for(uint32_t i=0;i<h->ncmds;i++){if(p>end||end-p<sizeof(load_command))return false;auto c=(const load_command*)p;if(c->cmdsize<sizeof(load_command)||c->cmdsize>end-p)return false;if(c->cmd==LC_UUID){if(c->cmdsize<sizeof(uuid_command)||found)return false;found=!memcmp(((const uuid_command*)c)->uuid,expected,sizeof(expected));}p+=c->cmdsize;}
 return found&&p==end&&hashMatches(base+151999,213,"d5a78812a5224dc620e0b9fddd2c2c4422a2399e18f994d67a10885f0b88a15b")&&hashMatches(base+146348,1136,"4c07b6daa5d9e4449c3f77192951ffa230915193befe87cbbf443e25226fa564");
}
__attribute__((noinline)) static const UInt8* observe(CFDataRef data){
 uintptr_t caller=(uintptr_t)__builtin_return_address(0);const UInt8*ret=CFDataGetBytePtr(data);int saved=errno;if(active){errno=saved;return ret;}active=true;
 Dl_info info{};const char*mode=getenv("KM_BOARD_MODE");bool calibration=mode&&!strcmp(mode,"calibration");bool actual=dladdr((void*)caller,&info)&&info.dli_fname&&strstr(info.dli_fname,"/AppleGVA")&&caller-(uintptr_t)info.dli_fbase==152101;bool pinned=actual&&validImage((uintptr_t)info.dli_fbase);
 if(calibration||actual){bool dataType=data&&CFGetTypeID(data)==CFDataGetTypeID();CFIndex length=dataType?CFDataGetLength(data):0;bool valid=ret&&length>0&&length<=63&&readable((uintptr_t)ret,(size_t)length);char board[64]{};if(valid){memcpy(board,ret,(size_t)length);if(board[length-1]==0)--length;board[length]=0;for(CFIndex i=0;i<length;i++)if(!((board[i]>='A'&&board[i]<='Z')||(board[i]>='a'&&board[i]<='z')||(board[i]>='0'&&board[i]<='9')||board[i]=='-'))valid=false;}if(!valid)strcpy(board,"INVALID");bool selection=false;if(actual&&pinned){void*frames[32];int count=backtrace(frames,32);for(int i=0;i<count;i++)if((uintptr_t)frames[i]==(uintptr_t)info.dli_fbase+146907)selection=true;}char line[256];int n=snprintf(line,sizeof(line),"KM_BOARD mode=%s profile=%d type=%d valid=%d selection=%d value=%s\n",actual?"gva":"calibration",pinned?1:0,dataType?1:0,valid?1:0,selection?1:0,board);if(n>0&&n<(int)sizeof(line))write(STDERR_FILENO,line,(size_t)n);}
 active=false;errno=saved;return ret;
}
__attribute__((used)) static const struct {const void*replacement;const void*original;} interpose __attribute__((section("__DATA,__interpose")))={(const void*)&observe,(const void*)&CFDataGetBytePtr};
