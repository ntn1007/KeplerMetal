// Triangle tessellation evaluation on SM30 using native tess coordinates.
#include <stdio.h>
#include "compiler/glsl_types.h"
#include "compiler/nir/nir.h"
#include "compiler/nir/nir_builder.h"
#include "nak.h"
#include "nv_device_info.h"
const struct nak_constant_offset_info nak_const_offsets_base={0};
const struct nak_constant_offset_info nak_const_offsets_turing_graphics={0};
int main(int argc,char**argv){
 if(argc!=3)return 1;struct nv_device_info device={.sm=30,.max_warps_per_mp=64,.cls_compute=0xa0c0,.cls_eng3d=0xa097};
 glsl_type_singleton_init_or_ref();struct nak_compiler*compiler=nak_compiler_create(&device);nir_builder b=nir_builder_init_simple_shader(MESA_SHADER_TESS_EVAL,nak_nir_options(compiler),"triangle_evaluation");
 b.shader->info.tess._primitive_mode=TESS_PRIMITIVE_TRIANGLES;b.shader->info.tess.spacing=TESS_SPACING_EQUAL;b.shader->info.tess.ccw=true;
 nir_def*coord=nir_load_tess_coord(&b),*u=nir_channel(&b,coord,0),*v=nir_channel(&b,coord,1),*w=nir_channel(&b,coord,2);
 nir_def*x=nir_fsub(&b,nir_fmul_imm(&b,v,3),nir_fadd(&b,u,w)),*y=nir_fsub(&b,nir_fmul_imm(&b,w,3),nir_fadd(&b,u,v));
 nir_def*position=nir_vec4(&b,x,y,nir_imm_float(&b,.5),nir_imm_float(&b,1));
 nir_def*color=nir_vec4(&b,nir_ffma(&b,nir_fmul(&b,u,u),nir_imm_float(&b,.5),nir_imm_float(&b,.125)),nir_ffma(&b,nir_fmul(&b,v,v),nir_imm_float(&b,.5),nir_imm_float(&b,.125)),nir_ffma(&b,nir_fmul(&b,w,w),nir_imm_float(&b,.5),nir_imm_float(&b,.125)),nir_imm_float(&b,1));
 nir_store_output(&b,position,nir_imm_int(&b,0),.base=0,.write_mask=15,.src_type=nir_type_float32,.io_semantics={.location=VARYING_SLOT_POS,.num_slots=1});
 nir_store_output(&b,color,nir_imm_int(&b,0),.base=1,.write_mask=15,.src_type=nir_type_float32,.io_semantics={.location=VARYING_SLOT_VAR0,.num_slots=1});
 b.shader->info.outputs_written=BITFIELD64_BIT(VARYING_SLOT_POS)|BITFIELD64_BIT(VARYING_SLOT_VAR0);
 nak_preprocess_nir(b.shader,compiler);struct nak_shader_bin*bin=nak_compile_shader(b.shader,true,compiler,0,NULL,false);
 if(!bin||bin->info.num_gprs>63||bin->info.slm_size||bin->info.crs_size)return 2;
 FILE*f=fopen(argv[1],"wb");if(!f)return 3;size_t n=fwrite(bin->code,1,bin->code_size,f);int s=fclose(f);if(n!=bin->code_size||s)return 3;
 f=fopen(argv[2],"w");if(!f)return 3;fputs(bin->asm_str,f);if(fclose(f))return 3;
 printf("{\"stage\":2,\"sm\":30,\"registers\":%u,\"code_bytes\":%u,\"scratch_bytes\":%u,\"crs_bytes\":%u}\n",bin->info.num_gprs,bin->code_size,bin->info.slm_size,bin->info.crs_size);
 nak_shader_bin_destroy(bin);ralloc_free(b.shader);nak_compiler_destroy(compiler);glsl_type_singleton_decref();return 0;
}
