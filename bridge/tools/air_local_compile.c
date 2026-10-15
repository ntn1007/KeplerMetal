// SPDX-License-Identifier: MIT
/* Bounded MSL/AIR local-memory compilation. No GPU access.
 * Shares the already-built OpenNVDA reader/lowerings and Mesa NAK libraries.
 * The ABI is explicit and must be matched by a separately validated carrier. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "compiler/glsl_types.h"
#include "compiler/nir/nir.h"
#include "compiler/nir/nir_builder.h"
#include "nak.h"
#include "nv_device_info.h"
#include "air_nir.h"

const struct nak_constant_offset_info nak_const_offsets_base = {0};
const struct nak_constant_offset_info nak_const_offsets_turing_graphics = {0};
static unsigned constant_bank;
static char output_path[8192];
static FILE *output(const char *directory, const char *name) {
    int length=snprintf(output_path,sizeof output_path,"%s/%s",directory,name);
    if(length<0 || length>=(int)sizeof output_path)return NULL;
    return fopen(output_path,"wb");
}
#include "KeplerLocalAIRLowering.inc"
static int print_air(air_module *module,const char *directory) {
    FILE *file=output(directory,"parsed-air.txt");if(!file)return 1;
    const char *names[]={"binop","cast","gep","select","extractelt","insertelt","shuffle",
        "cmp","ret","br","switch","unreachable","phi","alloca","load","store","call",
        "extractval","insertval","unop","atomicrmw","cmpxchg","fence","freeze"};
    for(unsigned f=0;f<module->nfunctions;f++) {
        air_function *fn=&module->functions[f];
        fprintf(file,"function %u %s prototype=%d args=%u blocks=%u\n",f,fn->name,fn->is_proto,fn->nargs,fn->nblocks);
        if(fn->is_proto)continue;
        for(unsigned i=0;i<fn->ninsts;i++) {
            air_inst *in=&fn->insts[i];
            fprintf(file,"  instruction %u block=%u value=%%%u op=%s sub=%u type=%u",i,in->bb,in->value,
                    in->op<sizeof names/sizeof names[0]?names[in->op]:"unknown",in->sub,in->type);
            if(in->op==AI_CALL && in->nops && in->ops[0]<fn->nvalues) {
                air_value *callee=&fn->values[in->ops[0]];
                if(callee->kind==AV_FUNCTION && callee->ival<module->nfunctions)
                    fprintf(file," callee=%s",module->functions[callee->ival].name);
            }
            for(unsigned j=0;j<in->nops;j++) {
                unsigned id=in->ops[j];fprintf(file," operand%u=%%%u",j,id);
                if(id>=fn->nvalues)continue;
                air_value *v=&fn->values[id];
                if(v->kind==AV_CINT)fprintf(file,"[constant=%llu]",(unsigned long long)v->ival);
                if(v->type<module->ntypes && module->types[v->type].kind==AT_PTR)
                    fprintf(file,"[address_space=%u]",module->types[v->type].addrspace);
            }
            fprintf(file,"\n");
        }
    }
    return fclose(file)!=0;
}
static bool uint32_type(air_module *m,unsigned type) {
    return type<m->ntypes && m->types[type].kind==AT_INT && m->types[type].bits==32;
}
static const air_md *local_md(air_module *m,int32_t id) {
    return id>=0 && (unsigned)id<m->nmd?&m->md[id]:NULL;
}
static bool local_entry_bindings(air_module *m,air_function *f) {
    const air_named_md *kernels=air_named(m,"air.kernel");
    for(unsigned i=0;kernels && i<kernels->n;i++) {
        const air_md *k=local_md(m,kernels->ops[i]);if(!k || k->kind!=AM_NODE || k->n<3)continue;
        const air_md *fn=local_md(m,k->ops[0]);if(!fn || fn->kind!=AM_VALUE || fn->value!=f->value)continue;
        const air_md *args=local_md(m,k->ops[2]);if(!args || args->kind!=AM_NODE || args->n!=4)return false;
        unsigned seen=0;
        for(unsigned j=0;j<args->n;j++) {
            const air_md *a=local_md(m,args->ops[j]);int64_t index=-1,location=-1;
            if(!a || a->kind!=AM_NODE || a->n<2 || air_md_int(m,a->ops[0],&index) ||
               index<0 || index>3 || (seen&(1u<<index)))return false;
            const char *kind=air_md_string(m,a->ops[1]);if(!kind)return false;
            if(index==3) {if(strcmp(kind,"air.thread_position_in_grid"))return false;}
            else {
                if(strcmp(kind,"air.buffer"))return false;
                for(unsigned z=2;z+1<a->n;z++) {
                    const char *key=air_md_string(m,a->ops[z]);
                    if(key && !strcmp(key,"air.location_index") && air_md_int(m,a->ops[z+1],&location))return false;
                }
                if(location!=index)return false;
            }
            seen|=1u<<index;
        }
        return seen==15;
    }
    return false;
}
static bool local_entry_contract(air_module *m,air_function *f) {
    if(f->nargs!=4 || f->first_arg>f->nvalues || f->nargs>f->nvalues-f->first_arg)return false;
    for(unsigned i=0;i<3;i++) {
        unsigned type=f->values[f->first_arg+i].type;
        if(type>=m->ntypes || m->types[type].kind!=AT_PTR ||
           m->types[type].addrspace!=(i==2?2u:1u))return false;
        unsigned elem=m->types[type].elem;if(elem>=m->ntypes)return false;
        if(i==0 && !uint32_type(m,elem))return false;
        if(i==1 && (m->types[elem].kind!=AT_VEC || m->types[elem].count!=4 ||
                     !uint32_type(m,m->types[elem].elem)))return false;
        if(i==2) {
            air_type *p=&m->types[elem];if(p->kind!=AT_STRUCT || p->count!=4 || p->packed)return false;
            for(unsigned j=0;j<4;j++)if(!uint32_type(m,p->members[j]))return false;
        }
    }
    return uint32_type(m,f->values[f->first_arg+3].type) && local_entry_bindings(m,f);
}
int main(int argc,char **argv) {
    if(argc!=6){fprintf(stderr,"usage: air_local_compile INPUT.air OUTDIR ENTRY LOCAL CONSTANT_BANK\n");return 2;}
    char *end=NULL;unsigned local=strtoul(argv[4],&end,10);if(!end||*end||!local||local>1024)return 2;
    constant_bank=strtoul(argv[5],&end,10);if(!end||*end||constant_bank!=KP_UNIFORM_CB)return 2;
    FILE *file=fopen(argv[1],"rb");if(!file)return 3;
    if(fseek(file,0,SEEK_END))return 4;long length=ftell(file);rewind(file);
    if(length<4||length>16*1024*1024)return 4;
    unsigned char *data=malloc(length);if(!data)return 5;
    if(fread(data,1,length,file)!=(size_t)length||fclose(file))return 6;
    char error[2048]={0};air_module module={0};
    if(air_read(data,length,&module,error,sizeof error)){fprintf(stderr,"AIR reader: %s\n",error);return 7;}
    if(print_air(&module,argv[2]))return 8;
    air_function *entry=NULL;
    for(unsigned i=0;i<module.nfunctions;i++)if(!module.functions[i].is_proto&&!strcmp(module.functions[i].name,argv[3]))entry=&module.functions[i];
    if(!entry)return 9;
    if(!local_entry_contract(&module,entry)){
        fprintf(stderr,"Unsupported local AIR entry types/address spaces\n");return 11;
    }
    struct nv_device_info device={.type=NV_DEVICE_TYPE_DIS,.device_id=0x1198,
        .device_name="GeForce GTX 880M",.chipset_name="GK104",.sm=30,.max_warps_per_mp=64,
        .cls_eng3d=0xa097,.cls_compute=0xa0c0,.max_smem_per_wg_kB=48,
        .sm_smem_sizes_kB={16,32,48},.sm_smem_size_count=3};
    glsl_type_singleton_init_or_ref();struct nak_compiler *compiler=nak_compiler_create(&device);
    air_variant variant={.block={local,1,1}};air_abi abi={0};
    nir_shader *shader=air_to_nir(&module,entry,nak_nir_options(compiler),&variant,&abi,error,sizeof error);
    if(!shader){fprintf(stderr,"AIR to NIR: %s\n",error);return 10;}
    if(shader->info.stage!=MESA_SHADER_COMPUTE||abi.nbuf!=3||abi.grid_offset!=24||abi.push_bytes!=48||abi.ntex||abi.nsamp||abi.cdata_bytes||abi.tg_bytes)return 11;
    shader->info.workgroup_size_variable=true;
    file=output(argv[2],"before-nak.nir.txt");if(!file)return 12;nir_print_shader(shader,file);if(fclose(file))return 12;
    NIR_PASS(_,shader,nir_lower_variable_initializers,nir_var_function_temp);
    NIR_PASS(_,shader,nir_lower_returns);NIR_PASS(_,shader,nir_inline_functions);
    NIR_PASS(_,shader,nir_opt_copy_prop);NIR_PASS(_,shader,nir_opt_constant_folding);
    NIR_PASS(_,shader,nir_opt_deref);nir_remove_non_entrypoints(shader);
    NIR_PASS(_,shader,nir_lower_variable_initializers,~0);NIR_PASS(_,shader,nir_split_var_copies);
    NIR_PASS(_,shader,nir_split_per_member_structs);
    /* Preserve dynamic thread arrays for the qualified local-memory importer. */
    NIR_PASS(_,shader,nir_lower_vars_to_ssa);
    NIR_PASS(_,shader,nir_opt_dce);nak_preprocess_nir(shader,compiler);
    nir_lower_compute_system_values_options system_values={.lower_local_invocation_index=true};
    NIR_PASS(_,shader,nir_lower_compute_system_values,&system_values);
    NIR_PASS(_,shader,nir_lower_explicit_io,nir_var_mem_push_const,nir_address_format_32bit_offset);
    NIR_PASS(_,shader,nir_shader_intrinsics_pass,lower_local_air_constants,nir_metadata_control_flow,NULL);
    NIR_PASS(_,shader,nir_opt_dce);
    NIR_PASS(_,shader,nir_shader_intrinsics_pass,lower_constants,nir_metadata_control_flow,NULL);
    NIR_PASS(_,shader,nir_opt_dce);NIR_PASS(_,shader,nir_remove_dead_derefs);
    NIR_PASS(_,shader,nir_lower_explicit_io,nir_var_mem_global,nir_address_format_64bit_global);
    nir_validate_shader(shader,"AIR local-memory offline SM30 harness");
    file=output(argv[2],"lowered.nir.txt");if(!file)return 12;nir_print_shader(shader,file);if(fclose(file))return 12;
    struct nak_shader_bin *binary=nak_compile_shader(shader,true,compiler,0,NULL,false);
    if(!binary||binary->info.sm!=30||!binary->code_size||binary->code_size%64||binary->info.num_gprs>63||binary->info.crs_size||binary->info.cs.smem_size)return 13;
    file=output(argv[2],"program.sass");if(!file)return 14;
    if(fwrite(binary->code,1,binary->code_size,file)!=binary->code_size||fclose(file))return 14;
    file=output(argv[2],"program.asm");if(!file)return 14;
    if(binary->asm_str)fputs(binary->asm_str,file);if(fclose(file))return 14;
    printf("{\"semantic\":\"%s\",\"source_language\":\"MSL/AIR\",\"sm\":30,\"code_bytes\":%u,\"registers\":%u,\"actual_registers\":%u,"
           "\"buffer_slots\":%u,\"grid_offset\":%u,\"push_bytes\":%u,\"scratch_bytes\":%u,\"crs_bytes\":%u,"
           "\"shared_bytes\":%u,\"control_barriers\":%u,\"spills_to_memory\":%u,\"fills_from_memory\":%u,\"gpu_execution\":false}\n",
           argv[3],binary->code_size,binary->info.num_gprs<24?24:binary->info.num_gprs,binary->info.num_gprs,
           abi.nbuf,abi.grid_offset,abi.push_bytes,binary->info.slm_size,binary->info.crs_size,
           binary->info.cs.smem_size,binary->info.num_control_barriers,binary->info.num_spills_to_mem,binary->info.num_fills_from_mem);
    nak_shader_bin_destroy(binary);ralloc_free(shader);nak_compiler_destroy(compiler);
    glsl_type_singleton_decref();free(abi.cdata);free(abi.refl);air_free(&module);free(data);return 0;
}
