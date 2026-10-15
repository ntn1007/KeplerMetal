/* Inspect actual AIR call types without translating or opening a GPU. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "airir.h"
int main(int argc,char **argv) {
    if(argc!=2)return 2;FILE *file=fopen(argv[1],"rb");if(!file)return 3;
    if(fseek(file,0,SEEK_END))return 4;long length=ftell(file);rewind(file);
    if(length<4||length>16*1024*1024)return 4;unsigned char *bytes=malloc(length);if(!bytes)return 5;
    if(fread(bytes,1,length,file)!=(size_t)length||fclose(file))return 6;
    char error[1024]={0};air_module m={0};if(air_read(bytes,length,&m,error,sizeof error)){fprintf(stderr,"%s\n",error);return 7;}
    printf("{\"scope\":\"offline AIR types only\",\"calls\":[");unsigned count=0;
    for(unsigned f=0;f<m.nfunctions;f++) {
        air_function *fn=&m.functions[f];if(fn->is_proto)continue;
        for(unsigned i=0;i<fn->ninsts;i++) {
            air_inst *in=&fn->insts[i];if(in->op!=AI_CALL||in->nops<4||in->ops[0]>=fn->nvalues)continue;
            air_value *callee=&fn->values[in->ops[0]];
            if(callee->kind!=AV_FUNCTION||callee->ival>=m.nfunctions)continue;
            const char *name=m.functions[callee->ival].name;if(!strstr(name,"cmpxchg"))continue;
            if(in->type>=m.ntypes||in->ops[1]>=fn->nvalues||in->ops[2]>=fn->nvalues)return 8;
            air_type *ret=&m.types[in->type],*obj=&m.types[fn->values[in->ops[1]].type],*exp=&m.types[fn->values[in->ops[2]].type];
            if(obj->kind!=AT_PTR||exp->kind!=AT_PTR||exp->elem>=m.ntypes)return 8;
            printf("%s{\"entry\":\"%s\",\"intrinsic\":\"%s\",\"return_kind\":%u,\"return_bits\":%u,"
                   "\"object_address_space\":%u,\"expected_address_space\":%u,\"expected_pointee_bits\":%u}",
                   count?",":"",fn->name,name,ret->kind,ret->bits,obj->addrspace,exp->addrspace,m.types[exp->elem].bits);count++;
        }
    }
    printf("]}\n");air_free(&m);free(bytes);return count==1?0:9;
}
