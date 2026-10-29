// SPDX-License-Identifier: MIT
// Calibrate on a null Mach port; no device receives these public IOKit calls.
#include <IOKit/IOKitLib.h>
#include <dlfcn.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "observer.h"

typedef void (*Snapshot)(struct KMDetails*);
static void need(int ok) { if(!ok) exit(1); }
int main(void) {
    Snapshot snapshot=(Snapshot)dlsym(RTLD_DEFAULT,"km_observer_details"); need(snapshot!=NULL);
    struct KMDetails *before=calloc(1,sizeof *before),*after=calloc(1,sizeof *after); need(before&&after);
    uint8_t in_bytes[3]={1,2,3},out_bytes[32]={0}; uint64_t in_scalars[2]={4,5},out_scalars[4]={0};
    size_t bytes=sizeof out_bytes; uint32_t scalars=4;
    snapshot(before);
    kern_return_t r0=IOConnectCallStructMethod(MACH_PORT_NULL,240,in_bytes,sizeof in_bytes,out_bytes,&bytes);
    snapshot(after); need(after->event_count==before->event_count+1);
    struct KMEvent e=after->events[before->event_count];
    need(e.kind==2 && e.selector==240 && e.service==KM_UNKNOWN_SERVICE && e.status==r0 &&
         e.input_struct==3 && (e.flags&12)==12 && e.struct_capacity==32 && e.struct_returned==bytes &&
         (e.flags&16) && strcmp(e.caller_image,"calibration")==0);
    *before=*after;
    kern_return_t r1=IOConnectCallScalarMethod(MACH_PORT_NULL,241,in_scalars,2,out_scalars,&scalars);
    snapshot(after); need(after->event_count==before->event_count+1); e=after->events[before->event_count];
    need(e.kind==3 && e.selector==241 && e.service==KM_UNKNOWN_SERVICE && e.status==r1 &&
         e.input_scalars==2 && (e.flags&3)==3 && e.scalar_capacity==4 && e.scalar_returned==scalars &&
         (e.flags&16) && strcmp(e.caller_image,"calibration")==0);
    bytes=sizeof out_bytes; scalars=4; *before=*after;
    kern_return_t r2=IOConnectCallMethod(MACH_PORT_NULL,242,in_scalars,2,in_bytes,sizeof in_bytes,
                                         out_scalars,&scalars,out_bytes,&bytes);
    snapshot(after); need(after->event_count==before->event_count+1); e=after->events[before->event_count];
    need(e.kind==1 && e.selector==242 && e.service==KM_UNKNOWN_SERVICE && e.status==r2 &&
         e.input_scalars==2 && e.input_struct==3 && (e.flags&15)==15 &&
         e.scalar_capacity==4 && e.scalar_returned==scalars && e.struct_capacity==32 && e.struct_returned==bytes &&
         (e.flags&16) && strcmp(e.caller_image,"calibration")==0);
    need(after->dropped==0); free(before); free(after);
    printf("{\"status\":\"PASS\",\"cases\":3,\"null_port_only\":true,\"returned_statuses\":[%d,%d,%d]}\n",r0,r1,r2);
    return 0;
}
