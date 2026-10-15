// Raw Kepler surface loads, followed by explicit format unpacking.
#include <stdio.h>
#include <string.h>
#include "compiler/glsl_types.h"
#include "compiler/nir/nir.h"
#include "compiler/nir/nir_builder.h"
#include "compiler/nir/nir_format_convert.h"
#include "nak.h"
#include "nak_private.h"
#include "nv_device_info.h"
#include "../src/KeplerResourceABI.h"
const struct nak_constant_offset_info nak_const_offsets_base={0};
const struct nak_constant_offset_info nak_const_offsets_turing_graphics={0};
static nir_def *cb(nir_builder *b,unsigned bank,unsigned offset,unsigned bits){return nir_ldc_nv(b,1,bits,nir_imm_int(b,bank),nir_imm_int(b,offset),.align_mul=bits/8);}
static nir_def *word(nir_builder *b,nir_def *base,unsigned offset){return nir_load_global(b,1,32,nir_iadd_imm(b,base,offset),.align_mul=4);}
int main(int argc,char **argv){
 if(argc!=4)return 1;enum pipe_format unpack,rawFormat;unsigned components;
 if(!strcmp(argv[1],"rgba32f")){unpack=PIPE_FORMAT_R32G32B32A32_FLOAT;rawFormat=PIPE_FORMAT_R32G32B32A32_UINT;components=4;}
 else if(!strcmp(argv[1],"rgba16f")){unpack=PIPE_FORMAT_R16G16B16A16_FLOAT;rawFormat=PIPE_FORMAT_R32G32_UINT;components=2;}
 else if(!strcmp(argv[1],"rgba8")){unpack=PIPE_FORMAT_R8G8B8A8_UNORM;rawFormat=PIPE_FORMAT_R32_UINT;components=1;}
 else if(!strcmp(argv[1],"r32f")){unpack=PIPE_FORMAT_R32_FLOAT;rawFormat=PIPE_FORMAT_R32_UINT;components=1;}
 else return 1;
 struct nv_device_info device={.sm=30,.max_warps_per_mp=64,.cls_compute=0xa0c0,.cls_eng3d=0xa097};glsl_type_singleton_init_or_ref();struct nak_compiler *compiler=nak_compiler_create(&device);
 nir_builder b=nir_builder_init_simple_shader(MESA_SHADER_COMPUTE,nak_nir_options(compiler),"surface_load_%s",argv[1]);b.shader->info.workgroup_size_variable=true;
 nir_def *local=nir_load_local_invocation_id(&b),*group=nir_load_workgroup_id(&b),*ids[2];
 for(unsigned axis=0;axis<2;axis++)ids[axis]=nir_iadd(&b,nir_iadd(&b,nir_imul(&b,nir_channel(&b,group,axis),cb(&b,1,KP_WORKGROUP_SIZE_OFFSET+axis*4,32)),nir_channel(&b,local,axis)),cb(&b,1,KP_GLOBAL_ORIGIN_OFFSET+axis*4,32));
 nir_def *width=cb(&b,2,32,32),*height=cb(&b,2,36,32);
 nir_push_if(&b,nir_iand(&b,nir_ult(&b,ids[0],width),nir_ult(&b,ids[1],height)));
 nir_def *x=nir_iadd(&b,ids[0],cb(&b,2,40,32)),*y=nir_iadd(&b,ids[1],cb(&b,2,44,32));
 nir_def *handle=cb(&b,1,KP_COMPUTE_TEXTURE0_HANDLE_OFFSET,32),*table=cb(&b,1,KP_SURFACE_TABLE_ADDRESS_OFFSET,64);
 nir_def *descriptor=nir_iadd(&b,table,nir_imul_imm(&b,nir_u2u64(&b,handle),KP_SURFACE_DESCRIPTOR_STRIDE));
 nir_def *base=word(&b,descriptor,0),*format=word(&b,descriptor,4),*clampX=word(&b,descriptor,8),*pitch=word(&b,descriptor,12),*clampY=word(&b,descriptor,16);
 const struct nak_nir_suclamp_flags flags={.mode=NAK_SUCLAMP_MODE_STORED_DESCRIPTOR,.round=NAK_SUCLAMP_ROUND_R1,.is_s32=true,.is_2d=true};
 nir_def *cx=nir_channel(&b,nir_suclamp_nv(&b,x,clampX,.flags=NAK_AS_U32(flags)),0),*cy=nir_channel(&b,nir_suclamp_nv(&b,y,clampY,.flags=NAK_AS_U32(flags)),0);
 const struct nak_nir_imadsp_flags mad={.params_from_src1=true};nir_def *offset=nir_imadsp_nv(&b,cy,pitch,cx,.flags=NAK_AS_U32(mad));
 nir_def *combined=nir_subfm_nv(&b,cx,cy,offset,.flags=0),*bf=nir_channel(&b,combined,0),*eau=nir_sueau_nv(&b,offset,bf,base);
 nir_def *oob=nir_ior(&b,nir_ine_imm(&b,nir_channel(&b,combined,1),0),nir_ieq_imm(&b,base,0));
 nir_def *raw=nir_suldga_nv(&b,components,nir_vec2(&b,bf,eau),format,oob,.format=rawFormat,.flags=NAK_SUGA_OFF_MODE_U8);
 nir_def *color=nir_format_unpack_rgba(&b,raw,unpack);
 color=nir_bcsel(&b,oob,nir_imm_vec4(&b,0,0,0,0),color);
 nir_def *output[4],*packed[4];for(unsigned c=0;c<4;c++){
  output[c]=nir_ffma(&b,nir_channel(&b,color,c),cb(&b,2,c*4,32),cb(&b,2,16+c*4,32));
  packed[c]=c<components?nir_channel(&b,raw,c):nir_imm_int(&b,0);
 }
 nir_def *index=nir_iadd(&b,nir_imul(&b,ids[1],width),ids[0]),*byteOffset=nir_ishl_imm(&b,nir_u2u64(&b,index),4);
 nir_store_global(&b,nir_vec(&b,output,4),nir_iadd(&b,cb(&b,1,KPResourceAddressOffset(7),64),byteOffset),.align_mul=16);
 nir_store_global(&b,nir_vec(&b,packed,4),nir_iadd(&b,cb(&b,1,KPResourceAddressOffset(8),64),byteOffset),.align_mul=16);nir_pop_if(&b,NULL);
 nak_preprocess_nir(b.shader,compiler);nir_lower_compute_system_values_options options={0};NIR_PASS(_,b.shader,nir_lower_compute_system_values,&options);
 struct nak_shader_bin *bin=nak_compile_shader(b.shader,true,compiler,0,NULL,false);if(!bin||bin->info.num_gprs>63||bin->info.slm_size||bin->info.crs_size)return 2;
 FILE *f=fopen(argv[2],"wb");if(!f)return 3;size_t n=fwrite(bin->code,1,bin->code_size,f);int s=fclose(f);if(n!=bin->code_size||s)return 3;
 f=fopen(argv[3],"w");if(!f)return 3;fputs(bin->asm_str,f);if(fclose(f))return 3;
 printf("{\"format\":\"%s\",\"sm\":30,\"registers\":%u,\"code_bytes\":%u,\"scratch_bytes\":%u,\"crs_bytes\":%u,\"raw_components\":%u}\n",argv[1],bin->info.num_gprs<24?24:bin->info.num_gprs,bin->code_size,bin->info.slm_size,bin->info.crs_size,components);
 nak_shader_bin_destroy(bin);ralloc_free(b.shader);nak_compiler_destroy(compiler);glsl_type_singleton_decref();return 0;
}
