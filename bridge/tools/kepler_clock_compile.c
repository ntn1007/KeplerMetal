// Shader-clock observation only; never modifies a clock or a hardware register.
#include <stdio.h>
#include "compiler/glsl_types.h"
#include "compiler/nir/nir.h"
#include "compiler/nir/nir_builder.h"
#include "nak.h"
#include "nv_device_info.h"
const struct nak_constant_offset_info nak_const_offsets_base={0};
const struct nak_constant_offset_info nak_const_offsets_turing_graphics={0};
int main(int argc,char**argv){
 if(argc!=3)return 1;
 struct nv_device_info device={.sm=30,.max_warps_per_mp=64,.cls_compute=0xa0c0,.cls_eng3d=0xa097};
 glsl_type_singleton_init_or_ref();struct nak_compiler*compiler=nak_compiler_create(&device);
 nir_builder b=nir_builder_init_simple_shader(MESA_SHADER_COMPUTE,nak_nir_options(compiler),"clock_observer");
 b.shader->info.workgroup_size[0]=1;b.shader->info.workgroup_size[1]=1;b.shader->info.workgroup_size[2]=1;
 nir_def*limit=nir_ldc_nv(&b,1,32,nir_imm_int(&b,2),nir_imm_int(&b,32),.align_mul=4,.align_offset=0);
 nir_def*output=nir_ldc_nv(&b,1,64,nir_imm_int(&b,2),nir_imm_int(&b,16),.align_mul=8,.align_offset=0);
 nir_def*begin=nir_pack_64_2x32(&b,nir_shader_clock(&b,.memory_scope=SCOPE_SUBGROUP));
 nir_variable*counter=nir_local_variable_create(b.impl,glsl_uint_type(),"counter"),*value=nir_local_variable_create(b.impl,glsl_float_type(),"value");
 nir_store_var(&b,counter,nir_imm_int(&b,0),1);nir_store_var(&b,value,nir_imm_float(&b,0.f),1);
 nir_push_loop(&b);nir_def*i=nir_load_var(&b,counter);
 nir_push_if(&b,nir_uge(&b,i,limit));nir_jump(&b,nir_jump_break);nir_pop_if(&b,NULL);
 nir_store_var(&b,value,nir_ffma(&b,nir_load_var(&b,value),nir_imm_float(&b,.99999f),nir_imm_float(&b,.125f)),1);
 nir_store_var(&b,counter,nir_iadd_imm(&b,i,1),1);nir_pop_loop(&b,NULL);
 nir_def*end=nir_pack_64_2x32(&b,nir_shader_clock(&b,.memory_scope=SCOPE_SUBGROUP));
 nir_store_global(&b,begin,output,.align_mul=8);
 nir_store_global(&b,end,nir_iadd_imm(&b,output,8),.align_mul=8);
 nir_store_global(&b,nir_load_var(&b,value),nir_iadd_imm(&b,output,16),.align_mul=4);
 NIR_PASS(_,b.shader,nir_lower_vars_to_ssa);nak_preprocess_nir(b.shader,compiler);
 nir_lower_compute_system_values_options opts={0};NIR_PASS(_,b.shader,nir_lower_compute_system_values,&opts);
 struct nak_shader_bin*bin=nak_compile_shader(b.shader,true,compiler,0,NULL,false);
 if(!bin||bin->info.sm!=30||bin->info.num_gprs>63||bin->info.slm_size||bin->info.crs_size)return 2;
 FILE*f=fopen(argv[1],"wb");if(!f)return 3;fwrite(bin->code,1,bin->code_size,f);fclose(f);
 f=fopen(argv[2],"w");if(!f)return 4;fputs(bin->asm_str,f);fclose(f);
 printf("{\"sm\":%u,\"registers\":%u,\"code_bytes\":%u,\"local_size\":[1,1,1]}\n",bin->info.sm,bin->info.num_gprs,bin->code_size);
 nak_shader_bin_destroy(bin);ralloc_free(b.shader);nak_compiler_destroy(compiler);glsl_type_singleton_decref();return 0;
}
