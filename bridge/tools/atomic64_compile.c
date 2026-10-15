// SM30 global integer atomic operations, with returned values and explicit CB2.
#include <stdio.h>
#include <string.h>
#include "compiler/glsl_types.h"
#include "compiler/nir/nir.h"
#include "compiler/nir/nir_builder.h"
#include "nak.h"
#include "nv_device_info.h"
const struct nak_constant_offset_info nak_const_offsets_base={0};
const struct nak_constant_offset_info nak_const_offsets_turing_graphics={0};
static nir_def *cb(nir_builder *b,unsigned offset,unsigned bits){return nir_ldc_nv(b,1,bits,nir_imm_int(b,2),nir_imm_int(b,offset),.align_mul=bits/8);}
int main(int argc,char **argv){
 if(argc!=4)return 1;bool drop=strstr(argv[1],"_drop")!=NULL;
 bool add=!strcmp(argv[1],"add")||!strcmp(argv[1],"add_drop"),cas=!strcmp(argv[1],"cas")||!strcmp(argv[1],"cas_drop"),exchange=!strcmp(argv[1],"exchange")||!strcmp(argv[1],"exchange_drop");if(!add&&!cas&&!exchange)return 1;
 struct nv_device_info device={.sm=30,.max_warps_per_mp=64,.cls_compute=0xa0c0,.cls_eng3d=0xa097};
 glsl_type_singleton_init_or_ref();struct nak_compiler *compiler=nak_compiler_create(&device);
 nir_builder b=nir_builder_init_simple_shader(MESA_SHADER_COMPUTE,nak_nir_options(compiler),"atomic64_%s",argv[1]);b.shader->info.workgroup_size[0]=32;b.shader->info.workgroup_size[1]=b.shader->info.workgroup_size[2]=1;
 nir_def *local=nir_channel(&b,nir_load_local_invocation_id(&b),0),*group=nir_channel(&b,nir_load_workgroup_id(&b),0);
 nir_def *index=nir_iadd(&b,nir_imul_imm(&b,group,32),local);
 nir_push_if(&b,nir_ult(&b,index,cb(&b,32,32)));
 nir_def *counter=cb(&b,16,64),*old;
 if(add)old=nir_global_atomic(&b,64,counter,nir_imm_int64(&b,0x100000003LL),.atomic_op=nir_atomic_op_iadd);
 else if(cas)old=nir_global_atomic_swap(&b,64,counter,nir_imm_int64(&b,0x2fffffff0LL),nir_imm_int64(&b,0x12345678abcdef00LL),.atomic_op=nir_atomic_op_cmpxchg);
 else{
  nir_def *value=nir_iadd_imm(&b,nir_imul_imm(&b,nir_u2u64(&b,index),0x100000009LL),0x12340000fffffff0LL);
  old=nir_global_atomic(&b,64,counter,value,.atomic_op=nir_atomic_op_xchg);
 }
 nir_def *destination=nir_iadd(&b,cb(&b,0,64),nir_ishl_imm(&b,nir_u2u64(&b,index),3));
 if(!drop)nir_store_global(&b,old,destination,.align_mul=8);
 nir_global_atomic(&b,32,cb(&b,24,64),nir_imm_int(&b,1),.atomic_op=nir_atomic_op_iadd);
 nir_pop_if(&b,NULL);
 nak_preprocess_nir(b.shader,compiler);nir_lower_compute_system_values_options options={0};NIR_PASS(_,b.shader,nir_lower_compute_system_values,&options);
 struct nak_shader_bin *bin=nak_compile_shader(b.shader,true,compiler,0,NULL,false);
 if(!bin||bin->info.sm!=30||bin->info.num_gprs>63||bin->info.slm_size||bin->info.crs_size)return 2;
 FILE *f=fopen(argv[2],"wb");if(!f)return 3;size_t n=fwrite(bin->code,1,bin->code_size,f);int status=fclose(f);if(n!=bin->code_size||status)return 3;
 f=fopen(argv[3],"w");if(!f)return 3;fputs(bin->asm_str,f);if(fclose(f))return 3;
 printf("{\"kind\":\"%s\",\"operation\":\"%s\",\"return_values\":%s,\"invocation_counter\":true,\"sm\":30,\"registers\":%u,\"code_bytes\":%u,\"scratch_bytes\":%u,\"crs_bytes\":%u}\n",argv[1],add?"add":(cas?"cas":"exchange"),drop?"false":"true",bin->info.num_gprs<24?24:bin->info.num_gprs,bin->code_size,bin->info.slm_size,bin->info.crs_size);
 nak_shader_bin_destroy(bin);ralloc_free(b.shader);nak_compiler_destroy(compiler);glsl_type_singleton_decref();return 0;
}
