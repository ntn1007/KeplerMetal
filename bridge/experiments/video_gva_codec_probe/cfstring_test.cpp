// SPDX-License-Identifier: MIT
#include "predicate.h"
#include <CoreFoundation/CoreFoundation.h>
#include <cassert>
#include <cstdio>
static CFTypeRef replacement(CFTypeRef original,bool allowed){
    if(original||!allowed)return original;
    return CFRetain(CFSTR("KeplerMetalProbe"));
}
int main(){
    CFTypeRef value=replacement(nullptr,KPCodecProbeAllowed("synthetic",true,150812,true,true,true,true,0));
    assert(value&&CFGetTypeID(value)==CFStringGetTypeID()&&CFEqual(value,CFSTR("KeplerMetalProbe")));
    char buf[32]{};assert(CFStringGetCString((CFStringRef)value,buf,sizeof(buf),kCFStringEncodingASCII));CFRelease(value);
    assert(!replacement(nullptr,KPCodecProbeAllowed("off",true,150812,true,true,true,true,0)));
    CFStringRef original=CFStringCreateWithCString(kCFAllocatorDefault,"existing",kCFStringEncodingASCII);
    assert(replacement(original,true)==original);CFRelease(original);
    std::puts("PASS CFString type ownership conversion and original preservation");
}
