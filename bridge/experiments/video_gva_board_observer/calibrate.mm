// SPDX-License-Identifier: MIT
#import <CoreFoundation/CoreFoundation.h>
#include <cstdio>
#include <cstring>
int main(){const UInt8 input[]="Mac-CALIBRATION";CFDataRef d=CFDataCreate(kCFAllocatorDefault,input,sizeof(input));if(!d)return 2;const UInt8*p=CFDataGetBytePtr(d);bool ok=p&&CFDataGetLength(d)==sizeof(input)&&!memcmp(p,input,sizeof(input));CFRelease(d);puts(ok?"CALIBRATION_PASS":"CALIBRATION_FAIL");return ok?0:1;}
