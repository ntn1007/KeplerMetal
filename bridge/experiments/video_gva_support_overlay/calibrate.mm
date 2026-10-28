// SPDX-License-Identifier: MIT
#import <CoreFoundation/CoreFoundation.h>
#include <cstdio>
#include <cstring>
int main(){const UInt8 input[]="Mac-CALIBRATION";CFDataRef d=CFDataCreate(kCFAllocatorDefault,input,sizeof(input));if(!d)return 2;const UInt8*p=CFDataGetBytePtr(d);bool ok=p&&CFDataGetLength(d)==sizeof(input)&&!memcmp(p,input,sizeof(input));CFRelease(d);const void*keys[]={CFSTR("KM-LOOKUP-CALIBRATION")};const void*values[]={CFSTR("known-value")};CFDictionaryRef dict=CFDictionaryCreate(kCFAllocatorDefault,keys,values,1,&kCFTypeDictionaryKeyCallBacks,&kCFTypeDictionaryValueCallBacks);const void*found=nullptr;bool got=dict&&CFDictionaryGetValueIfPresent(dict,keys[0],&found)&&found&&CFEqual((CFTypeRef)found,(CFTypeRef)values[0]);if(dict)CFRelease(dict);ok=ok&&got;puts(ok?"CALIBRATION_PASS":"CALIBRATION_FAIL");return ok?0:1;}
