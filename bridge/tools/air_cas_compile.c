/* Bounded offline AIR inspection and SM30 compilation. No GPU access.
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
static bool lower_constants(nir_builder *builder, nir_intrinsic_instr *instruction, void *unused) {
    (void)unused;
    if(instruction->intrinsic!=nir_intrinsic_load_push_constant)return false;
    builder->cursor=nir_before_instr(&instruction->instr);
    nir_def *offset=nir_iadd_imm(builder,instruction->src[0].ssa,nir_intrinsic_base(instruction));
    nir_def *value=nir_ldc_nv(builder,instruction->def.num_components,instruction->def.bit_size,
                            nir_imm_int(builder,constant_bank),offset,
                            .align_mul=instruction->def.bit_size/8,.align_offset=0);
    nir_def_rewrite_uses(&instruction->def,value);nir_instr_remove(&instruction->instr);
    return true;
}
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
int main(int argc,char **argv) {
    if(argc!=6){fprintf(stderr,"usage: air_cas_compile INPUT.air OUTDIR ENTRY LOCAL CONSTANT_BANK\n");return 2;}
    char *end=NULL;unsigned local=strtoul(argv[4],&end,10);if(!end||*end||!local||local>1024)return 2;
    constant_bank=strtoul(argv[5],&end,10);if(!end||*end||constant_bank>7)return 2;
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
    struct nv_device_info device={.type=NV_DEVICE_TYPE_DIS,.device_id=0x1198,
        .device_name="GeForce GTX 880M",.chipset_name="GK104",.sm=30,.max_warps_per_mp=64,
        .cls_eng3d=0xa097,.cls_compute=0xa0c0,.max_smem_per_wg_kB=48,
        .sm_smem_sizes_kB={16,32,48},.sm_smem_size_count=3};
    glsl_type_singleton_init_or_ref();struct nak_compiler *compiler=nak_compiler_create(&device);
    air_variant variant={.block={local,1,1}};air_abi abi={0};
    nir_shader *shader=air_to_nir(&module,entry,nak_nir_options(compiler),&variant,&abi,error,sizeof error);
    if(!shader){fprintf(stderr,"AIR to NIR: %s\n",error);return 10;}
    if(shader->info.stage!=MESA_SHADER_COMPUTE||abi.ntex||abi.nsamp||abi.cdata_bytes||abi.tg_bytes>49152)return 11;
    file=output(argv[2],"before-nak.nir.txt");if(!file)return 12;nir_print_shader(shader,file);if(fclose(file))return 12;
    NIR_PASS(_,shader,nir_lower_variable_initializers,nir_var_function_temp);
    NIR_PASS(_,shader,nir_lower_returns);NIR_PASS(_,shader,nir_inline_functions);
    NIR_PASS(_,shader,nir_opt_copy_prop);NIR_PASS(_,shader,nir_opt_constant_folding);
    NIR_PASS(_,shader,nir_opt_deref);nir_remove_non_entrypoints(shader);
    NIR_PASS(_,shader,nir_lower_variable_initializers,~0);NIR_PASS(_,shader,nir_split_var_copies);
    NIR_PASS(_,shader,nir_split_per_member_structs);
    /* AIR's next_expected temporary has a constant stack offset. Promote it
     * back to SSA when possible; the import does not promise scratch memory. */
    NIR_PASS(_,shader,nir_lower_scratch_to_var);NIR_PASS(_,shader,nir_lower_vars_to_ssa);
    NIR_PASS(_,shader,nir_opt_dce);nak_preprocess_nir(shader,compiler);
    nir_lower_compute_system_values_options system_values={.lower_local_invocation_index=true};
    NIR_PASS(_,shader,nir_lower_compute_system_values,&system_values);
    NIR_PASS(_,shader,nir_lower_explicit_io,nir_var_mem_push_const,nir_address_format_32bit_offset);
    NIR_PASS(_,shader,nir_shader_intrinsics_pass,lower_constants,nir_metadata_control_flow,NULL);
    NIR_PASS(_,shader,nir_opt_dce);NIR_PASS(_,shader,nir_remove_dead_derefs);
    NIR_PASS(_,shader,nir_lower_explicit_io,nir_var_mem_global,nir_address_format_64bit_global);
    nir_validate_shader(shader,"AIR CAS offline SM30 harness");
    file=output(argv[2],"lowered.nir.txt");if(!file)return 12;nir_print_shader(shader,file);if(fclose(file))return 12;
    struct nak_shader_bin *binary=nak_compile_shader(shader,true,compiler,0,NULL,false);
    if(!binary||binary->info.sm!=30||!binary->code_size||binary->code_size%64)return 13;
    file=output(argv[2],"program.sass");if(!file)return 14;
    if(fwrite(binary->code,1,binary->code_size,file)!=binary->code_size||fclose(file))return 14;
    file=output(argv[2],"program.asm");if(!file)return 14;
    if(binary->asm_str)fputs(binary->asm_str,file);if(fclose(file))return 14;
    printf("{\"sm\":30,\"code_bytes\":%u,\"registers\":%u,\"instructions\":%u,"
           "\"local_size\":[%u,%u,%u],\"buffer_slots\":%u,\"grid_offset\":%u,"
           "\"push_bytes\":%u,\"shared_bytes\":%u,\"constant_bank\":%u,"
           "\"scratch_bytes\":%u,\"crs_bytes\":%u,\"gpu_execution\":false}\n",
           binary->code_size,binary->info.num_gprs,binary->info.num_instrs,local,1,1,
           abi.nbuf,abi.grid_offset,abi.push_bytes,abi.tg_bytes,constant_bank,
           binary->info.slm_size,binary->info.crs_size);
    nak_shader_bin_destroy(binary);ralloc_free(shader);nak_compiler_destroy(compiler);
    glsl_type_singleton_decref();free(abi.cdata);free(abi.refl);air_free(&module);free(data);return 0;
}
