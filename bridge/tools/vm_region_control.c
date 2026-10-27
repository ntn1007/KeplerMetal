// SPDX-License-Identifier: MIT
// Own-process Mach VM control. Does not access IOKit or GPU memory.
#include <mach/mach.h>
#include <mach/mach_vm.h>
#include <mach/vm_region.h>
#include <stdio.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>

static int covers(mach_vm_address_t target) {
    mach_vm_address_t start=target;mach_vm_size_t size=0;
    vm_region_basic_info_data_64_t info={0};mach_msg_type_number_t count=VM_REGION_BASIC_INFO_COUNT_64;
    mach_port_t object=MACH_PORT_NULL;
    kern_return_t k=mach_vm_region(mach_task_self(),&start,&size,VM_REGION_BASIC_INFO_64,(vm_region_info_t)&info,&count,&object);
    if(object!=MACH_PORT_NULL)mach_port_deallocate(mach_task_self(),object);
    if(k==KERN_INVALID_ADDRESS)return 0;
    if(k!=KERN_SUCCESS)return -1;
    return start<=target && target-start<size;
}
int main(int argc,char**argv){
    if(argc!=2||(strcmp(argv[1],"positive")&&strcmp(argv[1],"reject")))return 2;
    mach_vm_size_t page=(mach_vm_size_t)getpagesize();mach_vm_address_t base=0;
    if(page==0 || page>1048576)return 3;
    kern_return_t k=mach_vm_allocate(mach_task_self(),&base,page*3,VM_FLAGS_ANYWHERE);
    if(k!=KERN_SUCCESS||!base)return 4;
    volatile uint8_t *lo=(uint8_t *)(uintptr_t)base,*hi=(uint8_t *)(uintptr_t)(base+page*2);
    *lo=0x35;*hi=0xca;
    int before=covers(base+page);int refused=!strcmp(argv[1],"reject");
    int called=0,after=-1,guard=0;int result=0;
    if(!refused){called=1;k=mach_vm_deallocate(mach_task_self(),base+page,page);after=covers(base+page);guard=covers(base)==1&&covers(base+page*2)==1&&*lo==0x35&&*hi==0xca;}
    else {after=covers(base+page);guard=*lo==0x35&&*hi==0xca;}
    if(before!=1||after!=(refused?1:0)||!guard||(!refused&&k!=KERN_SUCCESS))result=5;
    // Each call refers only to a range allocated by this process.
    kern_return_t cleanup;
    if(refused||k!=KERN_SUCCESS)cleanup=mach_vm_deallocate(mach_task_self(),base,page*3);
    else {kern_return_t a=mach_vm_deallocate(mach_task_self(),base,page);kern_return_t b=mach_vm_deallocate(mach_task_self(),base+page*2,page);cleanup=a?a:b;}
    if(cleanup!=KERN_SUCCESS)result=6;
    printf("{\"mode\":\"%s\",\"page_bytes\":%llu,\"target_present_before\":%s,\"target_present_after\":%s,\"target_deallocate_calls\":%d,\"adjacent_guards_preserved\":%s,\"cleanup_status\":%d,\"gpu_or_iokit_called\":false}\n",argv[1],(unsigned long long)page,before==1?"true":"false",after==1?"true":"false",called,guard?"true":"false",cleanup);
    return result;
}
