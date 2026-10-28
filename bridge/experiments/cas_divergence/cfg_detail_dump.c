/* Offline selected AIR function evidence, including control-flow block IDs. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "airir.h"
static void json_string(const char*s){putchar('"');for(const unsigned char*p=(const unsigned char*)s;*p;p++){if(*p=='"'||*p=='\\')printf("\\%c",*p);else if(*p<32)printf("\\u%04x",*p);else putchar(*p);}putchar('"');}
int main(int argc,char**argv){
 if(argc!=3||strlen(argv[2])>255)return 2;FILE*f=fopen(argv[1],"rb");if(!f)return 3;
 fseek(f,0,SEEK_END);long n=ftell(f);rewind(f);if(n<20||n>16*1024*1024)return 4;
 unsigned char*b=malloc(n);if(!b||fread(b,1,n,f)!=(size_t)n||fclose(f))return 5;
 air_module m={0};char error[1024]={0};if(air_read(b,n,&m,error,sizeof error)){fprintf(stderr,"%s\n",error);return 6;}
 air_function*fn=NULL;unsigned matches=0;
 for(unsigned i=0;i<m.nfunctions;i++)if(!m.functions[i].is_proto&&!strcmp(m.functions[i].name,argv[2])){fn=&m.functions[i];matches++;}
 if(matches!=1)return 7;
 printf("{\"types\":[");
 for(unsigned i=0;i<m.ntypes;i++){air_type*t=&m.types[i];printf("%s{\"kind\":%u,\"bits\":%u,\"element\":%u,\"count\":%u,\"address_space\":%u}",i?",":"",t->kind,t->bits,t->elem,t->count,t->addrspace);}
 printf("],\"functions\":[{\"name\":");json_string(fn->name);printf(",\"blocks\":%u,\"values\":[",fn->nblocks);
 for(unsigned i=0;i<fn->nvalues;i++){air_value*v=&fn->values[i];printf("%s{\"kind\":%u,\"type\":%u,\"integer\":%llu}",i?",":"",v->kind,v->type,(unsigned long long)v->ival);}
 printf("],\"instructions\":[");
 for(unsigned i=0;i<fn->ninsts;i++){
  air_inst*in=&fn->insts[i];printf("%s{\"index\":%u,\"op\":%u,\"block\":%u,\"value\":%u,\"type\":%u,\"operands\":[",i?",":"",i,in->op,in->bb,in->value,in->type);
  for(unsigned j=0;j<in->nops;j++)printf("%s%u",j?",":"",in->ops[j]);printf("],\"blocks\":[");
  for(unsigned j=0;j<in->nblocks;j++)printf("%s%u",j?",":"",in->blocks[j]);printf("],\"sub\":%u,\"flags\":%u,\"align\":%u",in->sub,in->flags,in->align);
  if(in->op==AI_CALL&&in->nops&&in->ops[0]<fn->nvalues){air_value*v=&fn->values[in->ops[0]];if(v->kind==AV_FUNCTION&&v->ival<m.nfunctions){printf(",\"callee\":");json_string(m.functions[v->ival].name);}}
  printf("}");
 }
 printf("]}]}\n");air_free(&m);free(b);return 0;
}
