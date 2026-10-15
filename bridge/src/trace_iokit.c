#include <IOKit/IOKitLib.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <pthread.h>
#include <stdarg.h>
#include <unistd.h>
#include <stdatomic.h>
static FILE* sink;
static pthread_mutex_t lock=PTHREAD_MUTEX_INITIALIZER;
static pthread_once_t once=PTHREAD_ONCE_INIT;
static unsigned long sequence;
static _Atomic uint32_t resource_connection;
static void record(const char*format,...);
static void record_bytes(const char*event,io_connect_t connection,uint32_t selector,const void*data,size_t size){
 if(!data||size>2048)return;const unsigned char*p=data;char hex[4097];
 for(size_t i=0;i<size;i++)snprintf(hex+2*i,3,"%02x",p[i]);hex[2*size]=0;
 record("\"event\":\"%s\",\"connection\":%u,\"selector\":%u,\"bytes\":%zu,\"hex\":\"%s\"",event,connection,selector,size,hex);
}
static void init(void){const char*p=getenv("KEPLER_TRACE_FILE");if(p)sink=fopen(p,"w");}
static void record(const char*format,...){pthread_once(&once,init);if(!sink)return;pthread_mutex_lock(&lock);fprintf(sink,"{\"sequence\":%lu,\"pid\":%d,",++sequence,getpid());va_list a;va_start(a,format);vfprintf(sink,format,a);va_end(a);fputs("}\n",sink);fflush(sink);pthread_mutex_unlock(&lock);}
void kepler_trace_mark(const char*label){record("\"event\":\"mark\",\"phase\":\"%s\"",label);}
static kern_return_t observed_open(io_service_t service,task_port_t task,uint32_t type,io_connect_t*connection){
 kern_return_t result=IOServiceOpen(service,task,type,connection);io_name_t name={0},cls={0};IORegistryEntryGetName(service,name);IOObjectGetClass(service,cls);
 if(result==0 && type==6 && !strcmp(name,"nvAccelerator"))atomic_store(&resource_connection,*connection);
 record("\"event\":\"open\",\"service\":\"%s\",\"class\":\"%s\",\"type\":%u,\"connection\":%u,\"status\":%u",name,cls,type,result==0?*connection:0,(unsigned)result);return result;
}
static kern_return_t observed_close(io_connect_t connection){kern_return_t r=IOServiceClose(connection);record("\"event\":\"close\",\"connection\":%u,\"status\":%u",connection,(unsigned)r);return r;}
static kern_return_t observed_method(mach_port_t connection,uint32_t selector,const uint64_t*input,uint32_t input_count,const void*input_struct,size_t input_size,uint64_t*output,uint32_t*output_count,void*output_struct,size_t*output_size){
 uint32_t output_capacity=output_count?*output_count:0;size_t struct_capacity=output_size?*output_size:0;
 if(connection==atomic_load(&resource_connection) && selector==0)
  record_bytes("resource_create_input",connection,selector,input_struct,input_size);
 /* Observe only the descriptor bytes already supplied by our own Metal probe.
  * Do not dereference addresses embedded in it, alter it, or replay it. */
 if(selector==1 && input_struct && input_size==32){
  const unsigned char*p=input_struct;char hex[65];
  for(size_t i=0;i<32;i++)snprintf(hex+2*i,3,"%02x",p[i]);
  record("\"event\":\"descriptor_observed\",\"connection\":%u,\"selector\":%u,\"bytes\":32,\"hex\":\"%s\"",connection,selector,hex);
 }
 kern_return_t r=IOConnectCallMethod(connection,selector,input,input_count,input_struct,input_size,output,output_count,output_struct,output_size);
 if(r==0 && connection==atomic_load(&resource_connection) && selector==0 && output_size && *output_size<=struct_capacity)
  record_bytes("resource_create_output",connection,selector,output_struct,*output_size);
 record("\"event\":\"method\",\"connection\":%u,\"selector\":%u,\"input_scalar_count\":%u,\"input_struct_bytes\":%zu,\"output_scalar_capacity\":%u,\"output_scalar_count\":%u,\"output_struct_capacity\":%zu,\"output_struct_bytes\":%zu,\"status\":%u",connection,selector,input_count,input_size,output_capacity,output_count?*output_count:0,struct_capacity,output_size?*output_size:0,(unsigned)r);return r;
}
static kern_return_t observed_map64(io_connect_t connection,uint32_t type,task_port_t task,mach_vm_address_t*address,mach_vm_size_t*size,IOOptionBits options){
 kern_return_t r=IOConnectMapMemory64(connection,type,task,address,size,options);record("\"event\":\"map64\",\"connection\":%u,\"memory_type\":%u,\"bytes\":%llu,\"options\":%u,\"status\":%u",connection,type,r==0?(unsigned long long)*size:0,(unsigned)options,(unsigned)r);return r;
}
static kern_return_t observed_map(io_connect_t connection,uint32_t type,task_port_t task,mach_vm_address_t*address,mach_vm_size_t*size,IOOptionBits options){
 kern_return_t r=IOConnectMapMemory(connection,type,task,address,size,options);record("\"event\":\"map\",\"connection\":%u,\"memory_type\":%u,\"bytes\":%llu,\"options\":%u,\"status\":%u",connection,type,r==0?(unsigned long long)*size:0,(unsigned)options,(unsigned)r);return r;
}
static kern_return_t observed_trap6(io_connect_t connection,uint32_t selector,uintptr_t a,uintptr_t b,uintptr_t c,uintptr_t d,uintptr_t e,uintptr_t f){kern_return_t r=IOConnectTrap6(connection,selector,a,b,c,d,e,f);record("\"event\":\"trap6\",\"connection\":%u,\"selector\":%u,\"status\":%u",connection,selector,(unsigned)r);return r;}
#define INTERPOSE(replacement,original) __attribute__((used)) static struct{const void* replacement;const void* original;} pair_##original __attribute__((section("__DATA,__interpose")))={(const void*)&replacement,(const void*)&original};
INTERPOSE(observed_open,IOServiceOpen)
INTERPOSE(observed_close,IOServiceClose)
INTERPOSE(observed_method,IOConnectCallMethod)
INTERPOSE(observed_map64,IOConnectMapMemory64)
INTERPOSE(observed_map,IOConnectMapMemory)
INTERPOSE(observed_trap6,IOConnectTrap6)
