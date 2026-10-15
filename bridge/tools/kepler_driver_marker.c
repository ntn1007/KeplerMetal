// Compile a diagnostic NIR shader using the installed driver's known output CB.
#include <stdio.h>
#include <string.h>
#include "compiler/glsl_types.h"
#include "compiler/nir/nir.h"
#include "compiler/nir/nir_builder.h"
#include "nak.h"
#include "nv_device_info.h"
const struct nak_constant_offset_info nak_const_offsets_base={0};
const struct nak_constant_offset_info nak_const_offsets_turing_graphics={0};
int main(int argc,char**argv){
 if(argc!=3&&argc!=4)return 1;bool straight=argc==4;
 bool add=argc==4&&!strcmp(argv[3],"add");
 struct nv_device_info device={.sm=30,.max_warps_per_mp=64,.cls_compute=0xa0c0,.cls_eng3d=0xa097};
 glsl_type_singleton_init_or_ref();struct nak_compiler*compiler=nak_compiler_create(&device);
 nir_builder builder=nir_builder_init_simple_shader(MESA_SHADER_COMPUTE,nak_nir_options(compiler),"driver_output_marker");
 builder.shader->info.workgroup_size[0]=32;builder.shader->info.workgroup_size[1]=1;builder.shader->info.workgroup_size[2]=1;
 if(!straight){
  nir_def*local=nir_channel(&builder,nir_load_local_invocation_id(&builder),0);
  nir_def*group=nir_channel(&builder,nir_load_workgroup_id(&builder),0);
  nir_push_if(&builder,nir_iand(&builder,nir_ieq_imm(&builder,local,0),nir_ieq_imm(&builder,group,0)));
 }
 nir_def*address=NULL,*value=NULL;
 if(add){
  nir_def*local=nir_channel(&builder,nir_load_local_invocation_id(&builder),0);
  nir_def*group=nir_channel(&builder,nir_load_workgroup_id(&builder),0);
  nir_def*index=nir_iadd(&builder,nir_imul_imm(&builder,group,32),local);
  nir_def*offset=nir_ishl_imm(&builder,nir_u2u64(&builder,index),2);
  nir_def*pa=nir_ldc_nv(&builder,1,64,nir_imm_int(&builder,2),nir_imm_int(&builder,0),.align_mul=8,.align_offset=0);
  nir_def*pb=nir_ldc_nv(&builder,1,64,nir_imm_int(&builder,2),nir_imm_int(&builder,8),.align_mul=8,.align_offset=0);
  nir_def*po=nir_ldc_nv(&builder,1,64,nir_imm_int(&builder,2),nir_imm_int(&builder,16),.align_mul=8,.align_offset=0);
  nir_def*va=nir_load_global(&builder,1,32,nir_iadd(&builder,pa,offset),.align_mul=4,.align_offset=0);
  nir_def*vb=nir_load_global(&builder,1,32,nir_iadd(&builder,pb,offset),.align_mul=4,.align_offset=0);
  address=nir_iadd(&builder,po,offset);value=nir_fadd(&builder,va,vb);
 }else{
  address=nir_ldc_nv(&builder,1,64,nir_imm_int(&builder,1),nir_imm_int(&builder,0x28),.align_mul=8,.align_offset=0);
  value=nir_imm_float(&builder,77.0f);
 }
 nir_store_global(&builder,value,address,.align_mul=4);
 if(!straight)nir_pop_if(&builder,NULL);
 nak_preprocess_nir(builder.shader,compiler);
 nir_lower_compute_system_values_options options={0};
 NIR_PASS(_,builder.shader,nir_lower_compute_system_values,&options);
 struct nak_shader_bin*binary=nak_compile_shader(builder.shader,true,compiler,0,NULL,false);
 if(!binary||binary->info.sm!=30||binary->info.num_gprs>24)return 2;
 FILE*file=fopen(argv[1],"wb");if(!file)return 3;fwrite(binary->code,1,binary->code_size,file);fclose(file);
 file=fopen(argv[2],"w");if(!file)return 4;if(binary->asm_str)fputs(binary->asm_str,file);fclose(file);
 printf("{\"sm\":%u,\"code_bytes\":%u,\"registers\":%u,\"kind\":\"%s\",\"scope\":\"offline NIR to SM30; host must bound dispatch\"}\n",binary->info.sm,binary->code_size,binary->info.num_gprs,add?"vector_add":(straight?"straight_marker":"branch_marker"));
 nak_shader_bin_destroy(binary);ralloc_free(builder.shader);nak_compiler_destroy(compiler);glsl_type_singleton_decref();return 0;
}
