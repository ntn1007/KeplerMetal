// Full-span shared memory exchanges and shared uint32 atomics on SM30.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "compiler/glsl_types.h"
#include "compiler/nir/nir.h"
#include "compiler/nir/nir_builder.h"
#include "nak.h"
#include "nv_device_info.h"
#include "../src/KeplerResourceABI.h"
const struct nak_constant_offset_info nak_const_offsets_base={0};
const struct nak_constant_offset_info nak_const_offsets_turing_graphics={0};
static nir_def *cb(nir_builder *b,unsigned bank,unsigned offset,unsigned bits){return nir_ldc_nv(b,1,bits,nir_imm_int(b,bank),nir_imm_int(b,offset),.align_mul=bits/8);}
static void barrier(nir_builder *b){nir_barrier(b,.execution_scope=SCOPE_WORKGROUP,.memory_scope=SCOPE_WORKGROUP,.memory_semantics=NIR_MEMORY_ACQ_REL,.memory_modes=nir_var_mem_shared);}
static nir_def *address(nir_builder *b,nir_def *base,nir_def *index){return nir_iadd(b,base,nir_ishl_imm(b,nir_u2u64(b,index),2));}
static nir_variable *start_loop(nir_builder *b,nir_def *local,unsigned words){
    nir_variable *i=nir_local_variable_create(b->impl,glsl_uint_type(),"i");nir_store_var(b,i,local,1);
    nir_push_loop(b);nir_break_if(b,nir_uge_imm(b,nir_load_var(b,i),words));return i;
}
static void end_loop(nir_builder *b,nir_variable *i,nir_def *local_size){nir_store_var(b,i,nir_iadd(b,nir_load_var(b,i),local_size),1);nir_pop_loop(b,NULL);}
int main(int argc,char **argv){
 if(argc!=5)return 1;const char *kind=argv[1];bool capacity=!strcmp(kind,"capacity"),add=!strcmp(kind,"add"),exchange=!strcmp(kind,"exchange"),cas=!strcmp(kind,"cas");
 if(!capacity&&!add&&!exchange&&!cas)return 1;unsigned bytes=(unsigned)strtoul(argv[4],NULL,10);
 if(capacity?(bytes!=16384&&bytes!=32768&&bytes!=49152):(bytes!=4))return 1;
 struct nv_device_info device={.sm=30,.max_warps_per_mp=64,.cls_compute=0xa0c0,.cls_eng3d=0xa097,.max_smem_per_wg_kB=48};
 glsl_type_singleton_init_or_ref();struct nak_compiler *compiler=nak_compiler_create(&device);
 nir_builder b=nir_builder_init_simple_shader(MESA_SHADER_COMPUTE,nak_nir_options(compiler),"shared_%s_%u",kind,bytes);
 b.shader->info.workgroup_size_variable=true;b.shader->info.shared_size=bytes;
 nir_def *local=nir_channel(&b,nir_load_local_invocation_id(&b),0),*group=nir_channel(&b,nir_load_workgroup_id(&b),0);
 nir_def *localSize=cb(&b,1,KP_WORKGROUP_SIZE_OFFSET,32),*base=cb(&b,2,0,64),*seed=cb(&b,2,8,32);
 nir_def *groupSalt=nir_imul_imm(&b,group,0x00100001u);
 if(capacity){
  unsigned words=bytes/4;nir_def *groupSeed=nir_ixor(&b,seed,groupSalt),*groupBase=nir_imul_imm(&b,group,words*2);
  for(unsigned phase=0;phase<2;phase++){
   nir_variable *i=start_loop(&b,local,words);nir_def *index=nir_load_var(&b,i);
   nir_def *value=nir_ixor(&b,nir_imul_imm(&b,index,0x9e3779b9u),groupSeed);if(phase)value=nir_ixor(&b,value,nir_imm_int(&b,0x6a09e667u));
   nir_store_shared(&b,value,nir_ishl_imm(&b,index,2),.align_mul=4);end_loop(&b,i,localSize);barrier(&b);
   i=start_loop(&b,local,words);index=nir_load_var(&b,i);
   nir_def *permutation=nir_umod(&b,nir_iadd_imm(&b,nir_imul_imm(&b,index,phase?7:5),phase?13:7),nir_imm_int(&b,words));
   value=nir_load_shared(&b,1,32,nir_ishl_imm(&b,permutation,2),.align_mul=4);
   nir_def *outputIndex=nir_iadd(&b,nir_iadd_imm(&b,groupBase,phase?words:0),index);
   nir_store_global(&b,value,address(&b,base,outputIndex),.align_mul=4);end_loop(&b,i,localSize);
   if(!phase)barrier(&b);
  }
 }else{
  nir_def *initial=nir_iadd(&b,seed,groupSalt),*active=cb(&b,2,12,32),*variant=cb(&b,2,16,32),*operand=cb(&b,2,20,32);
  nir_push_if(&b,nir_ieq_imm(&b,local,0));nir_store_shared(&b,initial,nir_imm_int(&b,0),.align_mul=4);nir_pop_if(&b,NULL);barrier(&b);
  nir_def *groupBase=nir_imul(&b,group,nir_iadd_imm(&b,localSize,1));
  nir_push_if(&b,nir_ult(&b,local,active));nir_def *previous;
  if(add)previous=nir_shared_atomic(&b,32,nir_imm_int(&b,0),nir_imm_int(&b,1),.atomic_op=nir_atomic_op_iadd);
  else if(exchange)previous=nir_shared_atomic(&b,32,nir_imm_int(&b,0),nir_ixor(&b,operand,local),.atomic_op=nir_atomic_op_xchg);
  else previous=nir_shared_atomic_swap(&b,32,nir_imm_int(&b,0),nir_ixor(&b,initial,nir_b2i32(&b,nir_ine_imm(&b,variant,0))),operand,.atomic_op=nir_atomic_op_cmpxchg);
  nir_store_global(&b,previous,address(&b,base,nir_iadd(&b,groupBase,local)),.align_mul=4);nir_pop_if(&b,NULL);barrier(&b);
  nir_push_if(&b,nir_ieq_imm(&b,local,0));
  nir_def *final=nir_load_shared(&b,1,32,nir_imm_int(&b,0),.align_mul=4);
  nir_store_global(&b,final,address(&b,base,nir_iadd(&b,groupBase,localSize)),.align_mul=4);nir_pop_if(&b,NULL);
 }
 NIR_PASS(_,b.shader,nir_lower_vars_to_ssa);nak_preprocess_nir(b.shader,compiler);
 nir_lower_compute_system_values_options options={0};NIR_PASS(_,b.shader,nir_lower_compute_system_values,&options);
 struct nak_shader_bin *bin=nak_compile_shader(b.shader,true,compiler,0,NULL,false);
 if(!bin||bin->info.sm!=30||bin->info.num_gprs>63||bin->info.slm_size||bin->info.crs_size||bin->info.cs.smem_size<bytes)return 2;
 FILE *f=fopen(argv[2],"wb");if(!f)return 3;size_t n=fwrite(bin->code,1,bin->code_size,f);if(fclose(f)||n!=bin->code_size)return 3;
 f=fopen(argv[3],"w");if(!f)return 3;fputs(bin->asm_str,f);if(fclose(f))return 3;
 printf("{\"kind\":\"%s\",\"sm\":30,\"registers\":%u,\"code_bytes\":%u,\"shared_bytes\":%u,\"control_barriers\":%u,\"scratch_bytes\":%u,\"crs_bytes\":%u}\n",kind,bin->info.num_gprs<24?24:bin->info.num_gprs,bin->code_size,bin->info.cs.smem_size,bin->info.num_control_barriers,bin->info.slm_size,bin->info.crs_size);
 nak_shader_bin_destroy(bin);ralloc_free(b.shader);nak_compiler_destroy(compiler);glsl_type_singleton_decref();return 0;
}
