// Resource-backed vertex/fragment fixtures and GPU indirect argument producer.
#include <stdio.h>
#include <string.h>
#include "compiler/glsl_types.h"
#include "compiler/nir/nir.h"
#include "compiler/nir/nir_builder.h"
#include "nak.h"
#include "nv_device_info.h"
const struct nak_constant_offset_info nak_const_offsets_base={0};
const struct nak_constant_offset_info nak_const_offsets_turing_graphics={0};
static nir_def* input(nir_builder*b,unsigned attribute){
 return nir_load_input(b,4,32,nir_imm_int(b,0),.base=attribute,.dest_type=nir_type_float32,
                       .io_semantics={.location=VERT_ATTRIB_GENERIC0+attribute,.num_slots=1});
}
static nir_def* constant(nir_builder*b,unsigned offset,unsigned bits){return nir_ldc_nv(b,1,bits,nir_imm_int(b,2),nir_imm_int(b,offset),.align_mul=bits/8);}
int main(int argc,char**argv){
 if(argc!=5)return 1;const char*kind=argv[1];bool vertex=!strcmp(kind,"vertex"),arguments=!strcmp(kind,"arguments"),smooth=!strcmp(kind,"smooth"),linear=!strcmp(kind,"linear"),flat=!strcmp(kind,"flat");
 if(!vertex&&!arguments&&!smooth&&!linear&&!flat)return 1;
 struct nv_device_info device={.sm=30,.max_warps_per_mp=64,.cls_compute=0xa0c0,.cls_eng3d=0xa097};
 glsl_type_singleton_init_or_ref();struct nak_compiler*compiler=nak_compiler_create(&device);
 mesa_shader_stage stage=vertex?MESA_SHADER_VERTEX:(arguments?MESA_SHADER_COMPUTE:MESA_SHADER_FRAGMENT);
 nir_builder b=nir_builder_init_simple_shader(stage,nak_nir_options(compiler),"io_%s",kind);
 if(vertex){
  nir_def*position=input(&b,0),*color=input(&b,1),*offset=input(&b,2),*instance=nir_load_instance_id(&b);
  // Installed Metal driver adds draw baseInstance in CB1[0x6c4].
  nir_def*instanceBase=nir_ldc_nv(&b,1,32,nir_imm_int(&b,1),nir_imm_int(&b,0x6c4),.align_mul=4);
  instance=nir_iadd(&b,instance,instanceBase);
  nir_def*w=nir_channel(&b,position,3);
  nir_def*x=nir_ffma(&b,nir_channel(&b,offset,0),w,nir_channel(&b,position,0));
  nir_def*y=nir_ffma(&b,nir_channel(&b,offset,1),w,nir_channel(&b,position,1));
  nir_def*outPosition=nir_vec4(&b,x,y,nir_channel(&b,position,2),w);
  nir_def*outColor=nir_fadd(&b,nir_fmul_imm(&b,color,.5),nir_imm_vec4(&b,.125,.125,.125,.5));
  nir_def*blue=nir_fadd(&b,nir_channel(&b,outColor,2),nir_fadd(&b,nir_fmul_imm(&b,nir_u2f32(&b,instance),1.f/32),nir_channel(&b,offset,2)));
  outColor=nir_vec4(&b,nir_channel(&b,outColor,0),nir_channel(&b,outColor,1),blue,nir_channel(&b,outColor,3));
  nir_store_output(&b,outPosition,nir_imm_int(&b,0),.base=0,.write_mask=15,.src_type=nir_type_float32,.io_semantics={.location=VARYING_SLOT_POS,.num_slots=1});
  nir_store_output(&b,outColor,nir_imm_int(&b,0),.base=1,.write_mask=15,.src_type=nir_type_float32,.io_semantics={.location=VARYING_SLOT_VAR0,.num_slots=1});
  b.shader->info.inputs_read=BITFIELD64_BIT(VERT_ATTRIB_GENERIC0)|BITFIELD64_BIT(VERT_ATTRIB_GENERIC1)|BITFIELD64_BIT(VERT_ATTRIB_GENERIC2);
  b.shader->info.outputs_written=BITFIELD64_BIT(VARYING_SLOT_POS)|BITFIELD64_BIT(VARYING_SLOT_VAR0);
 }else if(arguments){
  b.shader->info.workgroup_size[0]=32;b.shader->info.workgroup_size[1]=b.shader->info.workgroup_size[2]=1;
  nir_def*index=nir_channel(&b,nir_load_local_invocation_id(&b),0),*count=constant(&b,32,32);
  nir_push_if(&b,nir_ult(&b,index,count));
  nir_def*byteOffset=nir_ishl_imm(&b,nir_u2u64(&b,index),2);
  nir_def*seed=nir_load_global(&b,1,32,nir_iadd(&b,constant(&b,0,64),byteOffset),.align_mul=4);
  nir_store_global(&b,nir_ixor(&b,seed,nir_imm_int(&b,0x5a5a5a5a)),nir_iadd(&b,constant(&b,16,64),byteOffset),.align_mul=4);
  nir_pop_if(&b,NULL);
 }else{
  nir_def*color;
  if(flat)color=nir_load_input(&b,4,32,nir_imm_int(&b,0),.base=0,.dest_type=nir_type_float32,.io_semantics={.location=VARYING_SLOT_VAR0,.num_slots=1});
  else{
   nir_def*bary=nir_load_barycentric_pixel(&b,32,.interp_mode=smooth?INTERP_MODE_SMOOTH:INTERP_MODE_NOPERSPECTIVE);
   color=nir_load_interpolated_input(&b,4,32,bary,nir_imm_int(&b,0),.base=0,.dest_type=nir_type_float32,.io_semantics={.location=VARYING_SLOT_VAR0,.num_slots=1});
  }
  // Different fragment transform from the carrier, to identify imported execution.
  color=nir_fadd(&b,nir_fmul_imm(&b,color,.75),nir_imm_vec4(&b,.0625,.125,.1875,.25));
  nir_store_output(&b,color,nir_imm_int(&b,0),.base=0,.write_mask=15,.src_type=nir_type_float32,.io_semantics={.location=FRAG_RESULT_DATA0,.num_slots=1});
  b.shader->info.inputs_read=BITFIELD64_BIT(VARYING_SLOT_VAR0);b.shader->info.outputs_written=BITFIELD64_BIT(FRAG_RESULT_DATA0);
 }
 nak_preprocess_nir(b.shader,compiler);const struct nak_fs_key key={0};
 if(arguments){nir_lower_compute_system_values_options options={0};NIR_PASS(_,b.shader,nir_lower_compute_system_values,&options);}
 struct nak_shader_bin*bin=nak_compile_shader(b.shader,true,compiler,0,stage==MESA_SHADER_FRAGMENT?&key:NULL,false);
 if(!bin||bin->info.sm!=30||bin->info.num_gprs>63||bin->info.slm_size||bin->info.crs_size)return 2;
 const void*data[]={bin->code,bin->asm_str,bin->info.hdr};size_t sizes[]={bin->code_size,strlen(bin->asm_str),80};
 for(unsigned i=0;i<3;i++){FILE*f=fopen(argv[i+2],"wb");if(!f)return 3;if(fwrite(data[i],1,sizes[i],f)!=sizes[i]||fclose(f))return 3;}
 printf("{\"kind\":\"%s\",\"stage\":\"%s\",\"sm\":30,\"registers\":%u,\"code_bytes\":%u,\"scratch_bytes\":%u,\"crs_bytes\":%u}\n",kind,vertex?"vertex":(arguments?"compute":"fragment"),bin->info.num_gprs,bin->code_size,bin->info.slm_size,bin->info.crs_size);
 nak_shader_bin_destroy(bin);ralloc_free(b.shader);nak_compiler_destroy(compiler);glsl_type_singleton_decref();return 0;
}
