// SPDX-License-Identifier: MIT
#include <dlfcn.h>
extern "C" int KPLookupMarker(){return 42;}
extern "C" void *KPLookupControl(){return dlsym(RTLD_DEFAULT,"KPLookupMarker");}
