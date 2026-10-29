// SPDX-License-Identifier: MIT
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <dlfcn.h>
extern "C" __attribute__((noinline)) int kp_after_base(int x){return x+1;}
extern "C" __attribute__((noinline)) void kp_classify(){asm volatile("" ::: "memory");}
extern "C" __attribute__((noinline)) void kp_skip(){asm volatile("" ::: "memory");}
extern "C" __attribute__((noinline)) void kp_after_enumeration(){asm volatile("" ::: "memory");}
extern "C" void kp_invoke(uint32_t*,void*,int);
int main(int argc,char**argv){
 if(argc!=2&&argc!=3)return 2;
 void*lib=dlopen(argv[1],RTLD_NOW|RTLD_LOCAL);if(!lib)return 3;
 auto start=reinterpret_cast<void(*)(uintptr_t)>(dlsym(lib,"KPCalibrationStart"));if(!start)return 4;
 const char*mode=argc==3?argv[2]:"excluded";
 bool wrong=!std::strcmp(mode,"wrong"), accept=!std::strcmp(mode,"accept");
 if(!wrong&&!accept&&std::strcmp(mode,"excluded"))return 5;
 uintptr_t base=reinterpret_cast<uintptr_t>(&kp_after_base);start(base+(wrong?1:0));
 alignas(8) unsigned char node[0x464]={};uint32_t field=7,kind=accept?0x1080001:0x1040008;
 std::memcpy(node+0x428,&kind,4);node[0x460]=1;node[0x463]=1;
 kp_invoke(&field,node,accept?1:0);
 if(dlclose(lib))return 6;
 std::printf("cpu_value=%d\n",kp_after_base(21));return 0;
}
