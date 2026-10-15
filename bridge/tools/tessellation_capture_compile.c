// Buffer-only SM30 tessellation evaluation, using observed native CB1 bindings.
#include <stdio.h>
#include "compiler/glsl_types.h"
#include "compiler/nir/nir.h"
#include "compiler/nir/nir_builder.h"
#include "nak.h"
#include "nv_device_info.h"
#include "../src/KeplerResourceABI.h"
const struct nak_constant_offset_info nak_const_offsets_base={0};
const struct nak_constant_offset_info nak_const_offsets_turing_graphics={0};
static nir_def *address(nir_builder *b,unsigned binding) {
 return nir_ldc_nv(b,1,64,nir_imm_int(b,KP_RESOURCE_CB),nir_imm_int(b,KPResourceAddressOffset(binding)),.align_mul=8);
}
int main(int argc,char **argv) {
 if(argc!=3)return 1;
 struct nv_device_info device={.sm=30,.max_warps_per_mp=64,.cls_compute=0xa0c0,.cls_eng3d=0xa097};
 glsl_type_singleton_init_or_ref();struct nak_compiler *compiler=nak_compiler_create(&device);
 nir_builder b=nir_builder_init_simple_shader(MESA_SHADER_TESS_EVAL,nak_nir_options(compiler),"tessellation_capture");
 b.shader->info.tess._primitive_mode=TESS_PRIMITIVE_TRIANGLES;b.shader->info.tess.spacing=TESS_SPACING_EQUAL;b.shader->info.tess.ccw=true;
 nir_def *index=nir_global_atomic(&b,32,address(&b,0),nir_imm_int(&b,1),.atomic_op=nir_atomic_op_iadd);
 nir_push_if(&b,nir_ult_imm(&b,index,32768));
 nir_def *coord=nir_load_tess_coord(&b),*offset=nir_ishl_imm(&b,nir_u2u64(&b,index),4),*components[4];
 for(unsigned c=0;c<3;c++){
  nir_def *v=nir_channel(&b,coord,c);
  components[c]=nir_ffma(&b,nir_fmul(&b,v,v),nir_imm_float(&b,.5),nir_imm_float(&b,.125));
 }
 components[3]=nir_imm_float(&b,1);
 nir_store_global(&b,nir_vec4(&b,nir_channel(&b,coord,0),nir_channel(&b,coord,1),nir_channel(&b,coord,2),nir_imm_float(&b,1)),nir_iadd(&b,address(&b,1),offset),.align_mul=16);
 nir_store_global(&b,nir_vec(&b,components,4),nir_iadd(&b,address(&b,2),offset),.align_mul=16);
 nir_pop_if(&b,NULL);
 nak_preprocess_nir(b.shader,compiler);struct nak_shader_bin *bin=nak_compile_shader(b.shader,true,compiler,0,NULL,false);
 if(!bin||bin->info.num_gprs>63||bin->info.slm_size||bin->info.crs_size)return 2;
 FILE *f=fopen(argv[1],"wb");if(!f)return 3;size_t n=fwrite(bin->code,1,bin->code_size,f);int status=fclose(f);if(n!=bin->code_size||status)return 3;
 f=fopen(argv[2],"w");if(!f)return 3;fputs(bin->asm_str,f);if(fclose(f))return 3;
 printf("{\"stage\":2,\"registers\":%u,\"code_bytes\":%u,\"scratch_bytes\":%u,\"crs_bytes\":%u}\n",bin->info.num_gprs,bin->code_size,bin->info.slm_size,bin->info.crs_size);
 nak_shader_bin_destroy(bin);ralloc_free(b.shader);nak_compiler_destroy(compiler);glsl_type_singleton_decref();return 0;
}
