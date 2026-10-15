/* Offline typed AIR evidence for conservative native CAS diagnosis; no NAK. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "airir.h"
int main(int argc,char**argv){
 if(argc!=2)return 2;FILE*f=fopen(argv[1],"rb");if(!f)return 3;
 fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);if(n<4||n>16*1024*1024)return 4;
 unsigned char*b=malloc(n);if(!b||fread(b,1,n,f)!=(size_t)n||fclose(f))return 5;
 air_module m={0};char e[1024]={0};if(air_read(b,n,&m,e,sizeof e)){fprintf(stderr,"%s\n",e);return 6;}
 printf("{\"types\":[");
 for(unsigned i=0;i<m.ntypes;i++){air_type*t=&m.types[i];printf("%s{\"kind\":%u,\"bits\":%u,\"element\":%u,\"count\":%u,\"address_space\":%u}",i?",":"",t->kind,t->bits,t->elem,t->count,t->addrspace);}
 printf("],\"functions\":[");unsigned count=0;
 for(unsigned f=0;f<m.nfunctions;f++){air_function*fn=&m.functions[f];if(fn->is_proto)continue;
  if(strcmp(fn->name,"test"))return 7;
  printf("%s{\"name\":\"test\",\"blocks\":%u,\"values\":[",count++?",":"",fn->nblocks);
  for(unsigned i=0;i<fn->nvalues;i++){air_value*v=&fn->values[i];printf("%s{\"kind\":%u,\"type\":%u,\"integer\":%llu}",i?",":"",v->kind,v->type,(unsigned long long)v->ival);}
  printf("],\"instructions\":[");
  for(unsigned i=0;i<fn->ninsts;i++){air_inst*in=&fn->insts[i];printf("%s{\"index\":%u,\"op\":%u,\"block\":%u,\"value\":%u,\"type\":%u,\"operands\":[",i?",":"",i,in->op,in->bb,in->value,in->type);
   for(unsigned j=0;j<in->nops;j++)printf("%s%u",j?",":"",in->ops[j]);printf("]");
   if(in->op==AI_CALL&&in->nops&&in->ops[0]<fn->nvalues){air_value*v=&fn->values[in->ops[0]];if(v->kind==AV_FUNCTION&&v->ival<m.nfunctions)printf(",\"callee\":\"%s\"",m.functions[v->ival].name);}
   printf("}");
  }printf("]}");
 }
 printf("]}\n");air_free(&m);free(b);return count==1?0:8;
}
