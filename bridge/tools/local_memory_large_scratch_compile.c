// SPDX-License-Identifier: MIT
// Direct NIR reference for the same local-array/live-value uint32 semantics.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "compiler/glsl_types.h"
#include "compiler/nir/nir.h"
#include "compiler/nir/nir_builder.h"
#include "nak.h"
#include "nv_device_info.h"
#include "KeplerResourceABI.h"
const struct nak_constant_offset_info nak_const_offsets_base={0};
const struct nak_constant_offset_info nak_const_offsets_turing_graphics={0};
static nir_def*cb(nir_builder*b,unsigned bank,unsigned offset,unsigned bits){return nir_ldc_nv(b,1,bits,nir_imm_int(b,bank),nir_imm_int(b,offset),.align_mul=bits/8);}
static nir_def*rot(nir_builder*b,nir_def*x){return nir_ior(b,nir_ishl_imm(b,x,5),nir_ushr_imm(b,x,27));}
static nir_def*global(nir_builder*b,nir_def*base,nir_def*i){return nir_load_global(b,1,32,nir_iadd(b,base,nir_ishl_imm(b,nir_u2u64(b,i),2)),.align_mul=4,.access=ACCESS_VOLATILE);}
static nir_variable*loop(nir_builder*b,unsigned count){nir_variable*i=nir_local_variable_create(b->impl,glsl_uint_type(),"i");nir_store_var(b,i,nir_imm_int(b,0),1);nir_push_loop(b);nir_break_if(b,nir_uge_imm(b,nir_load_var(b,i),count));return i;}
static void end(nir_builder*b,nir_variable*i){nir_store_var(b,i,nir_iadd_imm(b,nir_load_var(b,i),1),1);nir_pop_loop(b,NULL);}
int main(int argc,char**argv){
 if(argc!=4)return 1;bool pressure=!strncmp(argv[1],"pressure",8),control=!strcmp(argv[1],"local_control");unsigned words=control?0:strtoul(argv[1]+(pressure?8:5),NULL,10);
 if(pressure?(words!=32&&words!=64&&words!=96):(!control&&words!=32&&words!=256&&words!=1024&&words!=2048&&words!=4096))return 1;
 struct nv_device_info device={.sm=30,.max_warps_per_mp=64,.cls_compute=0xa0c0,.cls_eng3d=0xa097};glsl_type_singleton_init_or_ref();struct nak_compiler*compiler=nak_compiler_create(&device);
 nir_builder b=nir_builder_init_simple_shader(MESA_SHADER_COMPUTE,nak_nir_options(compiler),"local_memory_%s",argv[1]);b.shader->info.workgroup_size_variable=true;b.shader->scratch_size=pressure?0:words*4;
 nir_def*gid=nir_iadd(&b,nir_imul(&b,nir_channel(&b,nir_load_workgroup_id(&b),0),cb(&b,1,KP_WORKGROUP_SIZE_OFFSET,32)),nir_channel(&b,nir_load_local_invocation_id(&b),0));
 gid=nir_iadd(&b,gid,cb(&b,1,KP_GLOBAL_ORIGIN_OFFSET,32));nir_def*seed=cb(&b,2,0,32),*n=cb(&b,2,4,32),*stride=cb(&b,2,8,32),*input=cb(&b,1,KPResourceAddressOffset(0),64),*output=cb(&b,1,KPResourceAddressOffset(1),64),*base=nir_imul(&b,gid,stride);
 // The guard is retained: structured-control import is part of the contract.
 // Pressure kernels still require uniform full groups because of their barrier.
 nir_push_if(&b,nir_ult(&b,gid,n));nir_def*state=NULL,*checksum=NULL;
 if(pressure){
  nir_def*values[96];for(unsigned i=0;i<words;i++)values[i]=global(&b,input,nir_iadd_imm(&b,base,i));
  nir_barrier(&b,.execution_scope=SCOPE_WORKGROUP,.memory_scope=SCOPE_WORKGROUP,.memory_semantics=NIR_MEMORY_ACQ_REL,.memory_modes=nir_var_mem_global);
  state=nir_ixor(&b,global(&b,input,nir_iadd_imm(&b,base,128)),seed);checksum=nir_ixor(&b,state,gid);
  for(unsigned i=0;i<words;i++)checksum=nir_iadd(&b,rot(&b,nir_ixor(&b,checksum,values[i])),nir_ixor(&b,state,nir_imm_int(&b,i*2891336453u)));
 }else{
  nir_def*initial=nir_ixor(&b,nir_ixor(&b,global(&b,input,base),seed),nir_imul_imm(&b,gid,747796405u));
  if(control){state=initial;checksum=rot(&b,state);}
  else{
   nir_variable*s=nir_local_variable_create(b.impl,glsl_uint_type(),"state"),*sum=nir_local_variable_create(b.impl,glsl_uint_type(),"checksum");nir_store_var(&b,s,initial,1);
   nir_variable*i=loop(&b,words);nir_def*index=nir_load_var(&b,i),*v=nir_ixor(&b,nir_iadd(&b,initial,nir_imul_imm(&b,index,2891336453u)),nir_iadd_imm(&b,nir_imul_imm(&b,index,22695477u),0x11998877u));nir_store_scratch(&b,v,nir_ishl_imm(&b,index,2),.align_mul=4);end(&b,i);
   i=loop(&b,17);nir_def*turn=nir_load_var(&b,i),*old=nir_load_var(&b,s);index=nir_iand_imm(&b,nir_ixor(&b,old,nir_imul_imm(&b,turn,97)),words-1);nir_def*other=nir_iand_imm(&b,nir_iadd_imm(&b,index,13),words-1),*a=nir_load_scratch(&b,1,32,nir_ishl_imm(&b,index,2),.align_mul=4),*c=nir_load_scratch(&b,1,32,nir_ishl_imm(&b,other,2),.align_mul=4),*next=nir_iadd(&b,rot(&b,nir_ixor(&b,a,c)),nir_ixor(&b,old,turn));nir_store_scratch(&b,next,nir_ishl_imm(&b,index,2),.align_mul=4);nir_store_var(&b,s,nir_ixor(&b,nir_iadd_imm(&b,nir_imul_imm(&b,next,1664525u),1013904223u),c),1);end(&b,i);
   state=nir_load_var(&b,s);nir_store_var(&b,sum,state,1);i=loop(&b,words);index=nir_load_var(&b,i);v=nir_load_scratch(&b,1,32,nir_ishl_imm(&b,index,2),.align_mul=4);nir_store_var(&b,sum,nir_iadd(&b,rot(&b,nir_ixor(&b,nir_load_var(&b,sum),v)),index),1);end(&b,i);checksum=nir_load_var(&b,sum);
  }
 }
 nir_def*result=nir_vec4(&b,checksum,state,nir_imm_int(&b,words),nir_ixor(&b,gid,nir_imm_int(&b,0xcafe0000u)));nir_store_global(&b,result,nir_iadd(&b,output,nir_ishl_imm(&b,nir_u2u64(&b,gid),4)),.align_mul=16);nir_pop_if(&b,NULL);
 NIR_PASS(_,b.shader,nir_lower_vars_to_ssa);nak_preprocess_nir(b.shader,compiler);nir_lower_compute_system_values_options options={0};NIR_PASS(_,b.shader,nir_lower_compute_system_values,&options);
 struct nak_shader_bin*bin=nak_compile_shader(b.shader,true,compiler,0,NULL,false);if(!bin||bin->info.sm!=30||bin->info.num_gprs>63||bin->info.crs_size||bin->info.cs.smem_size)return 2;
 FILE*f=fopen(argv[2],"wb");if(!f)return 3;size_t nbytes=fwrite(bin->code,1,bin->code_size,f);if(fclose(f)||nbytes!=bin->code_size)return 3;f=fopen(argv[3],"w");if(!f)return 3;fputs(bin->asm_str,f);if(fclose(f))return 3;
 printf("{\"semantic\":\"%s\",\"uniform_full_workgroups_required\":true,\"sm\":30,\"registers\":%u,\"actual_registers\":%u,\"code_bytes\":%u,\"scratch_bytes\":%u,\"crs_bytes\":%u,\"control_barriers\":%u,\"spills_to_memory\":%u,\"fills_from_memory\":%u}\n",argv[1],bin->info.num_gprs<24?24:bin->info.num_gprs,bin->info.num_gprs,bin->code_size,bin->info.slm_size,bin->info.crs_size,bin->info.num_control_barriers,bin->info.num_spills_to_mem,bin->info.num_fills_from_mem);
 nak_shader_bin_destroy(bin);ralloc_free(b.shader);nak_compiler_destroy(compiler);glsl_type_singleton_decref();return 0;
}
