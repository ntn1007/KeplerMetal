// Controlled SM30 compute kernels with an explicit macOS CB2 resource ABI.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "compiler/glsl_types.h"
#include "compiler/nir/nir.h"
#include "compiler/nir/nir_builder.h"
#include "nak.h"
#include "nv_device_info.h"
const struct nak_constant_offset_info nak_const_offsets_base={0};
const struct nak_constant_offset_info nak_const_offsets_turing_graphics={0};
static nir_def *constant(nir_builder*b,unsigned offset,unsigned bits){return nir_ldc_nv(b,1,bits,nir_imm_int(b,2),nir_imm_int(b,offset),.align_mul=bits/8,.align_offset=0);}
static nir_def *address(nir_builder*b,nir_def*base,nir_def*index,unsigned shift){return nir_iadd(b,base,nir_ishl_imm(b,nir_u2u64(b,index),shift));}
static void barrier(nir_builder*b){nir_barrier(b,.execution_scope=SCOPE_WORKGROUP,.memory_scope=SCOPE_WORKGROUP,.memory_semantics=NIR_MEMORY_ACQ_REL,.memory_modes=nir_var_mem_shared);}
int main(int argc,char**argv){
 if(argc!=4&&argc!=5){fprintf(stderr,"usage: kepler_compute_suite KIND OUT.sass OUT.asm [MATRIX_SIZE]\n");return 1;}
 const char*kind=argv[1];bool fp64=!strcmp(kind,"fp64"),atomic=!strcmp(kind,"atomic32"),shared=!strcmp(kind,"shared_reduce"),shuffle=!strcmp(kind,"shuffle"),counted=!strcmp(kind,"tiled_counted"),tiled=!strcmp(kind,"tiled_matmul")||counted,matrix=!strcmp(kind,"matmul")||tiled;
 if(!fp64&&!atomic&&!shared&&!shuffle&&!matrix)return 1;
 unsigned size=argc==5?(unsigned)strtoul(argv[4],NULL,10):64,logSize=0;
 if(matrix&&(size<(tiled?16:8)||size>1024||(size&(size-1))))return 1;
 while((1u<<logSize)<size)logSize++;
 struct nv_device_info device={.sm=30,.max_warps_per_mp=64,.cls_compute=0xa0c0,.cls_eng3d=0xa097,.max_smem_per_wg_kB=48};
 glsl_type_singleton_init_or_ref();struct nak_compiler*compiler=nak_compiler_create(&device);
 nir_builder b=nir_builder_init_simple_shader(MESA_SHADER_COMPUTE,nak_nir_options(compiler),"%s",kind);
 b.shader->info.workgroup_size[0]=tiled?256:(shared?128:32);b.shader->info.workgroup_size[1]=1;b.shader->info.workgroup_size[2]=1;
 nir_def*local=nir_channel(&b,nir_load_local_invocation_id(&b),0),*group=nir_channel(&b,nir_load_workgroup_id(&b),0);
 nir_def*index=nir_iadd(&b,nir_imul_imm(&b,group,32),local),*count=constant(&b,32,32);
 nir_def*pa=constant(&b,0,64),*pb=constant(&b,8,64),*po=constant(&b,16,64);
 if(tiled){
  if(counted){nir_push_if(&b,nir_iand(&b,nir_ieq_imm(&b,local,0),nir_ieq_imm(&b,group,0)));nir_global_atomic(&b,32,constant(&b,24,64),nir_imm_int(&b,1),.atomic_op=nir_atomic_op_iadd);nir_pop_if(&b,NULL);}
  b.shader->info.shared_size=2048;
  nir_def*tx=nir_iand_imm(&b,local,15),*ty=nir_ushr_imm(&b,local,4);
  nir_def*tileRow=nir_ushr_imm(&b,group,logSize-4),*tileCol=nir_iand_imm(&b,group,size/16-1);
  nir_def*row=nir_iadd(&b,nir_ishl_imm(&b,tileRow,4),ty),*col=nir_iadd(&b,nir_ishl_imm(&b,tileCol,4),tx);
  nir_variable*tile=nir_local_variable_create(b.impl,glsl_uint_type(),"tile"),*acc=nir_local_variable_create(b.impl,glsl_float_type(),"acc");
  nir_store_var(&b,tile,nir_imm_int(&b,0),1);nir_store_var(&b,acc,nir_imm_float(&b,0),1);
  nir_push_loop(&b);nir_def*k=nir_load_var(&b,tile);
  nir_push_if(&b,nir_uge_imm(&b,k,size));nir_jump(&b,nir_jump_break);nir_pop_if(&b,NULL);
  nir_def*ia=nir_iadd(&b,nir_imul_imm(&b,row,size),nir_iadd(&b,k,tx));
  nir_def*ib=nir_iadd(&b,nir_imul_imm(&b,nir_iadd(&b,k,ty),size),col);
  nir_def*a=nir_load_global(&b,1,32,address(&b,pa,ia,2),.align_mul=4,.align_offset=0);
  nir_def*c=nir_load_global(&b,1,32,address(&b,pb,ib,2),.align_mul=4,.align_offset=0);
  nir_def*slot=nir_ishl_imm(&b,local,2);
  nir_store_shared(&b,a,slot,.align_mul=4,.align_offset=0);nir_store_shared(&b,c,nir_iadd_imm(&b,slot,1024),.align_mul=4,.align_offset=0);barrier(&b);
  for(unsigned j=0;j<16;j++){
   nir_def*as=nir_load_shared(&b,1,32,nir_iadd_imm(&b,nir_ishl_imm(&b,ty,6),j*4),.align_mul=4,.align_offset=0);
   nir_def*bs=nir_load_shared(&b,1,32,nir_iadd_imm(&b,nir_ishl_imm(&b,tx,2),1024+j*64),.align_mul=4,.align_offset=0);
   nir_store_var(&b,acc,nir_ffma(&b,as,bs,nir_load_var(&b,acc)),1);
  }
  barrier(&b);nir_store_var(&b,tile,nir_iadd_imm(&b,k,16),1);nir_pop_loop(&b,NULL);
  nir_def*outputIndex=nir_iadd(&b,nir_imul_imm(&b,row,size),col);
  nir_store_global(&b,nir_load_var(&b,acc),address(&b,po,outputIndex,2),.align_mul=4);
 }else if(shared){
  // Uniform full groups; every invocation reaches every workgroup barrier.
  b.shader->info.shared_size=512;
  nir_def*slot=nir_ishl_imm(&b,local,2);
  nir_store_shared(&b,nir_u2f32(&b,nir_iadd_imm(&b,local,2)),slot,.align_mul=4,.align_offset=0);
  barrier(&b);
  for(unsigned stride=64;stride;stride/=2){
   nir_push_if(&b,nir_ult_imm(&b,local,stride));
   nir_def*a=nir_load_shared(&b,1,32,slot,.align_mul=4,.align_offset=0);
   nir_def*c=nir_load_shared(&b,1,32,nir_iadd_imm(&b,slot,stride*4),.align_mul=4,.align_offset=0);
   nir_store_shared(&b,nir_fadd(&b,a,c),slot,.align_mul=4,.align_offset=0);
   nir_pop_if(&b,NULL);barrier(&b);
  }
  nir_push_if(&b,nir_ieq_imm(&b,local,0));
  nir_def*sum=nir_load_shared(&b,1,32,nir_imm_int(&b,0),.align_mul=4,.align_offset=0);
  nir_store_global(&b,sum,address(&b,po,group,2),.align_mul=4);nir_pop_if(&b,NULL);
 }else if(shuffle){
  // Host dispatches complete warps. Output lane receives lane xor 16.
  nir_def*value=nir_shuffle_xor(&b,nir_iadd_imm(&b,local,1),nir_imm_int(&b,16));
  nir_store_global(&b,value,address(&b,po,index,2),.align_mul=4);
 }else{
  nir_push_if(&b,nir_ult(&b,index,count));
  if(atomic){
   nir_global_atomic(&b,32,po,nir_imm_int(&b,1),.atomic_op=nir_atomic_op_iadd);
  }else if(matrix){
   nir_def*row=nir_ushr_imm(&b,index,logSize),*col=nir_iand_imm(&b,index,size-1);
   nir_variable*k=nir_local_variable_create(b.impl,glsl_uint_type(),"k"),*acc=nir_local_variable_create(b.impl,glsl_float_type(),"acc");
   nir_store_var(&b,k,nir_imm_int(&b,0),1);nir_store_var(&b,acc,nir_imm_float(&b,0),1);
   nir_push_loop(&b);
   nir_def*iteration=nir_load_var(&b,k);
   nir_push_if(&b,nir_uge_imm(&b,iteration,size));nir_jump(&b,nir_jump_break);nir_pop_if(&b,NULL);
   nir_def*ia=nir_iadd(&b,nir_imul_imm(&b,row,size),iteration),*ib=nir_iadd(&b,nir_imul_imm(&b,iteration,size),col);
   nir_def*a=nir_load_global(&b,1,32,address(&b,pa,ia,2),.align_mul=4,.align_offset=0);
   nir_def*c=nir_load_global(&b,1,32,address(&b,pb,ib,2),.align_mul=4,.align_offset=0);
   nir_store_var(&b,acc,nir_fadd(&b,nir_load_var(&b,acc),nir_fmul(&b,a,c)),1);
   nir_store_var(&b,k,nir_iadd_imm(&b,iteration,1),1);nir_pop_loop(&b,NULL);
   nir_store_global(&b,nir_load_var(&b,acc),address(&b,po,index,2),.align_mul=4);
  }else{
   nir_def*a=nir_load_global(&b,1,64,address(&b,pa,index,3),.align_mul=8,.align_offset=0);
   nir_def*c=nir_load_global(&b,1,64,address(&b,pb,index,3),.align_mul=8,.align_offset=0);
   nir_store_global(&b,nir_fadd(&b,a,c),address(&b,po,index,3),.align_mul=8);
  }
  nir_pop_if(&b,NULL);
 }
 NIR_PASS(_,b.shader,nir_lower_vars_to_ssa);
 nak_preprocess_nir(b.shader,compiler);nir_lower_compute_system_values_options options={0};
 NIR_PASS(_,b.shader,nir_lower_compute_system_values,&options);
 struct nak_shader_bin*bin=nak_compile_shader(b.shader,true,compiler,0,NULL,false);
 if(!bin||bin->info.sm!=30||bin->info.num_gprs>63||bin->info.slm_size||bin->info.crs_size)return 2;
 FILE*f=fopen(argv[2],"wb");if(!f)return 3;size_t written=fwrite(bin->code,1,bin->code_size,f);if(fclose(f)||written!=bin->code_size)return 3;
 f=fopen(argv[3],"w");if(!f)return 4;if(bin->asm_str)fputs(bin->asm_str,f);if(fclose(f))return 4;
 printf("{\"kind\":\"%s\",\"sm\":%u,\"code_bytes\":%u,\"registers\":%u,\"control_barriers\":%u,\"shared_bytes\":%u,\"scratch_bytes\":%u,\"crs_bytes\":%u,\"matrix_size\":%u,\"local_size\":[%u,1,1]}\n",kind,bin->info.sm,bin->code_size,bin->info.num_gprs,bin->info.num_control_barriers,bin->info.cs.smem_size,bin->info.slm_size,bin->info.crs_size,matrix?size:0,bin->info.cs.local_size[0]);
 nak_shader_bin_destroy(bin);ralloc_free(b.shader);nak_compiler_destroy(compiler);glsl_type_singleton_decref();return 0;
}
