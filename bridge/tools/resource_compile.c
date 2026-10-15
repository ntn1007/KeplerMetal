// SM30 resource access using the observed installed driver's CB1/CB2 ABI.
#include <stdio.h>
#include <string.h>
#include "compiler/glsl_types.h"
#include "compiler/nir/nir.h"
#include "compiler/nir/nir_builder.h"
#include "nak.h"
#include "nak_private.h"
#include "nv_device_info.h"
#include "../src/KeplerResourceABI.h"
const struct nak_constant_offset_info nak_const_offsets_base={0};
const struct nak_constant_offset_info nak_const_offsets_turing_graphics={0};
static nir_def*cb(nir_builder*b,unsigned binding,unsigned offset,unsigned bits){return nir_ldc_nv(b,1,bits,nir_imm_int(b,binding),nir_imm_int(b,offset),.align_mul=bits/8);}
static nir_def*word(nir_builder*b,nir_def*address,unsigned offset){return nir_load_global(b,1,32,nir_iadd_imm(b,address,offset),.align_mul=4);}
int main(int argc,char**argv){
 if(argc!=4)return 1;bool image=!strcmp(argv[1],"image"),a=!strcmp(argv[1],"buffers_a"),bLayout=!strcmp(argv[1],"buffers_b");if(!image&&!a&&!bLayout)return 1;
 struct nv_device_info device={.sm=30,.max_warps_per_mp=64,.cls_compute=0xa0c0,.cls_eng3d=0xa097};glsl_type_singleton_init_or_ref();struct nak_compiler*compiler=nak_compiler_create(&device);
 nir_builder b=nir_builder_init_simple_shader(MESA_SHADER_COMPUTE,nak_nir_options(compiler),"resource_%s",argv[1]);
 b.shader->info.workgroup_size_variable=true;
 nir_def*local=nir_load_local_invocation_id(&b),*group=nir_load_workgroup_id(&b),*ids[3];
 for(unsigned axis=0;axis<3;axis++)ids[axis]=nir_iadd(&b,nir_iadd(&b,nir_imul(&b,nir_channel(&b,group,axis),cb(&b,KP_RESOURCE_CB,KP_WORKGROUP_SIZE_OFFSET+axis*4,32)),nir_channel(&b,local,axis)),cb(&b,KP_RESOURCE_CB,KP_GLOBAL_ORIGIN_OFFSET+axis*4,32));
 nir_def*x=ids[0],*y=ids[1],*z=ids[2];
 if(!image){
  nir_def*w=cb(&b,KP_UNIFORM_CB,32,32),*h=cb(&b,KP_UNIFORM_CB,36,32),*d=cb(&b,KP_UNIFORM_CB,40,32);
  nir_push_if(&b,nir_iand(&b,nir_ult(&b,x,w),nir_iand(&b,nir_ult(&b,y,h),nir_ult(&b,z,d))));
  nir_def*index=nir_iadd(&b,nir_imul(&b,nir_iadd(&b,nir_imul(&b,z,h),y),w),x),*offset=nir_ishl_imm(&b,nir_u2u64(&b,index),4);
  unsigned input=a?0:5,output=a?7:2;
  nir_def*value=nir_load_global(&b,4,32,nir_iadd(&b,cb(&b,KP_RESOURCE_CB,KPResourceAddressOffset(input),64),offset),.align_mul=16);
  nir_def*components[4];for(unsigned c=0;c<4;c++){nir_def*base=nir_ffma(&b,nir_channel(&b,value,c),cb(&b,KP_UNIFORM_CB,c*4,32),cb(&b,KP_UNIFORM_CB,16+c*4,32));components[c]=nir_fadd_imm(&b,base,(c+1)/8.f);}
  nir_store_global(&b,nir_vec(&b,components,4),nir_iadd(&b,cb(&b,KP_RESOURCE_CB,KPResourceAddressOffset(output),64),offset),.align_mul=16);
  nir_pop_if(&b,NULL);
 }else{
  nir_def*handle=cb(&b,KP_RESOURCE_CB,KP_COMPUTE_TEXTURE0_HANDLE_OFFSET,32),*table=cb(&b,KP_RESOURCE_CB,KP_SURFACE_TABLE_ADDRESS_OFFSET,64);
  nir_def*descriptor=nir_iadd(&b,table,nir_imul_imm(&b,nir_u2u64(&b,handle),KP_SURFACE_DESCRIPTOR_STRIDE));
  nir_def*base=word(&b,descriptor,KP_SURFACE_ADDRESS_SHIFTED8_OFFSET),*format=word(&b,descriptor,KP_SURFACE_FORMAT_OFFSET),*clampX=word(&b,descriptor,KP_SURFACE_CLAMP_X_OFFSET),*pitch=word(&b,descriptor,KP_SURFACE_PITCH_OFFSET),*clampY=word(&b,descriptor,KP_SURFACE_CLAMP_Y_OFFSET);
  const struct nak_nir_suclamp_flags flags={.mode=NAK_SUCLAMP_MODE_STORED_DESCRIPTOR,.round=NAK_SUCLAMP_ROUND_R1,.is_s32=true,.is_2d=true};
  nir_def*cx=nir_channel(&b,nir_suclamp_nv(&b,x,clampX,.flags=NAK_AS_U32(flags)),0),*cy=nir_channel(&b,nir_suclamp_nv(&b,y,clampY,.flags=NAK_AS_U32(flags)),0);
  const struct nak_nir_imadsp_flags madFlags={.params_from_src1=true};
  nir_def*off=nir_imadsp_nv(&b,cy,pitch,cx,.flags=NAK_AS_U32(madFlags));
  nir_def*combined=nir_subfm_nv(&b,cx,cy,off,.flags=0),*bf=nir_channel(&b,combined,0),*eau=nir_sueau_nv(&b,off,bf,base);
  nir_def*oob=nir_ior(&b,nir_ine_imm(&b,nir_channel(&b,combined,1),0),nir_ieq_imm(&b,base,0));
  nir_def*color=nir_vec4(&b,nir_fmul_imm(&b,nir_u2f32(&b,nir_iadd_imm(&b,x,5)),1.f/64),nir_fmul_imm(&b,nir_u2f32(&b,nir_iadd_imm(&b,y,3)),1.f/48),nir_imm_float(&b,.75f),nir_imm_float(&b,1));
  nir_sustga_nv(&b,nir_vec2(&b,bf,eau),format,oob,color,.flags=NAK_SUGA_OFF_MODE_U8);
 }
 nak_preprocess_nir(b.shader,compiler);nir_lower_compute_system_values_options options={0};NIR_PASS(_,b.shader,nir_lower_compute_system_values,&options);
 struct nak_shader_bin*bin=nak_compile_shader(b.shader,true,compiler,0,NULL,false);if(!bin||bin->info.num_gprs>63||bin->info.slm_size||bin->info.crs_size)return 2;
 FILE*f=fopen(argv[2],"wb");if(!f)return 3;size_t n=fwrite(bin->code,1,bin->code_size,f);int status=fclose(f);if(n!=bin->code_size||status)return 3;
 f=fopen(argv[3],"w");if(!f)return 3;fputs(bin->asm_str,f);if(fclose(f))return 3;
 printf("{\"kind\":\"%s\",\"sm\":30,\"registers\":%u,\"code_bytes\":%u,\"local_size_variable\":true,\"scratch_bytes\":%u,\"crs_bytes\":%u}\n",argv[1],bin->info.num_gprs,bin->code_size,bin->info.slm_size,bin->info.crs_size);
 nak_shader_bin_destroy(bin);ralloc_free(b.shader);nak_compiler_destroy(compiler);glsl_type_singleton_decref();return 0;
}
