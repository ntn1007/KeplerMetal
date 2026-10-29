// SPDX-License-Identifier: MIT
#include <cstdlib>
#include <malloc/malloc.h>
extern "C" __attribute__((noinline)) void KPForeignFree(void *p){std::free(p);}
extern "C" __attribute__((noinline)) void KPForeignZoneFree(malloc_zone_t *z,void *p){malloc_zone_free(z,p);}
