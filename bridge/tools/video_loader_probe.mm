// Load the installed user-space VA bundle in our own process; call no vendor ABI.
#import <Foundation/Foundation.h>
#include <dlfcn.h>
#include <mach-o/dyld.h>
#include <cstring>
#include <cstdio>
int main(){@autoreleasepool{
 const char *path="/System/Library/Extensions/GeForceVADriver.bundle/Contents/MacOS/GeForceVADriver";
 dlerror();void *handle=dlopen(path,RTLD_NOW|RTLD_LOCAL);const char *error=dlerror();
 NSString *loaderError=error?@(error):@"";
 NSMutableArray *images=[NSMutableArray array];for(uint32_t i=0;i<_dyld_image_count();i++){const char *name=_dyld_get_image_name(i);if(strstr(name,"GVA")||strstr(name,"GeForceVA")||strstr(name,"VideoToolbox"))[images addObject:@(name)];}
 NSDictionary *result=@{@"path":@(path),@"loaded":@(handle!=nullptr),@"loader_error":loaderError,@"loaded_images":images,@"vendor_function_called":@NO,@"hardware_execution_proved":@NO,@"scope":@"Own-process user-space loader only; no system file changes or unknown vendor calls; no code-page byte reads"};
 NSData *json=[NSJSONSerialization dataWithJSONObject:result options:NSJSONWritingPrettyPrinted error:nil];fwrite(json.bytes,1,json.length,stdout);puts("");if(handle)dlclose(handle);return 0;
}}
