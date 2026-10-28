// SPDX-License-Identifier: MIT
// CFDictionary permits opaque pointer keys when callbacks are null.
#import <CoreFoundation/CoreFoundation.h>
#include <dlfcn.h>
#include <cstdio>
int main(){auto arm=(void(*)(const void*))dlsym(RTLD_DEFAULT,"KMGVAArmCalibration");if(!arm)return 2;CFStringRef known=CFSTR("KM-LOOKUP-CALIBRATION");arm(known);const void*key=(const void*)0x1234;const void*value=(const void*)0x5678;CFDictionaryRef d=CFDictionaryCreate(kCFAllocatorDefault,&key,&value,1,nullptr,nullptr);if(!d)return 3;const void*out=nullptr;bool ok=CFDictionaryGetValueIfPresent(d,key,&out)&&out==value;CFRelease(d);puts(ok?"OPAQUE_PASS":"OPAQUE_FAIL");return ok?0:4;}
