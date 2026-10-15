// Minimal fragment NIR -> NAK/SM30. Native render transport remains driver-owned.
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "compiler/glsl_types.h"
#include "compiler/nir/nir.h"
#include "compiler/nir/nir_builder.h"
#include "nak.h"
#include "nv_device_info.h"
#include "nak_private.h"
extern struct nak_shader_bin *nak_compile_shader_embedded(nir_shader*,bool,const struct nak_compiler*,nir_variable_mode,const struct nak_fs_key*,bool,void(*)(nir_shader*,void*),void*);
struct binding_context {bool failed;unsigned count;};
static bool bound_texture(nir_builder*b,nir_instr*instr,void*data){
 if(instr->type!=nir_instr_type_tex)return false;
 struct binding_context*context=data;nir_tex_instr*tex=nir_instr_as_tex(instr);struct nak_nir_tex_flags flags;
 memcpy(&flags,&tex->backend_flags,sizeof flags);
 if(tex->num_srcs!=1||tex->src[0].src_type!=nir_tex_src_backend1||flags.ref_type!=NAK_NIR_TEX_REF_TYPE_BINDLESS){context->failed=true;return false;}
 nir_def*src=tex->src[0].src.ssa;nir_scalar handle=nir_scalar_resolved(src,0);
 if(!nir_scalar_is_const(handle)||nir_scalar_as_uint(handle)!=0x001000e0){context->failed=true;return false;}
 b->cursor=nir_before_instr(instr);
 nir_def*coordinates=nir_vec4(b,nir_channel(b,src,1),nir_channel(b,src,2),nir_channel(b,src,3),nir_imm_int(b,0));
 nir_src_rewrite(&tex->src[0].src,coordinates);flags.ref_type=NAK_NIR_TEX_REF_TYPE_BOUND;
 tex->texture_index=0x01e0;memcpy(&tex->backend_flags,&flags,sizeof flags);context->count++;return true;
}
static void adapt_bindings(nir_shader*shader,void*data){
 NIR_PASS(_,shader,nir_shader_instructions_pass,bound_texture,nir_metadata_control_flow,data);
 NIR_PASS(_,shader,nir_opt_dce);
}
const struct nak_constant_offset_info nak_const_offsets_base={0};
const struct nak_constant_offset_info nak_const_offsets_turing_graphics={0};
int main(int argc,char**argv){
 if(argc!=4&&argc!=5)return 1;const char*kind=argc==5?argv[4]:"constant";
 bool read=!strcmp(kind,"read"),nearest=!strcmp(kind,"nearest"),linear=!strcmp(kind,"linear"),half=!strcmp(kind,"vertex_half"),near=!strcmp(kind,"vertex_near"),far=!strcmp(kind,"vertex_far"),vertex=!strcmp(kind,"vertex")||half||near||far,texture=read||nearest||linear;
 bool blend=!strcmp(kind,"blend"),red=!strcmp(kind,"constant_red"),masked=!strncmp(kind,"mask",4),mrt=!strncmp(kind,"mrt",3);
 unsigned renderTargets=mrt?(unsigned)atoi(kind+3):1, sampleMask=masked?(unsigned)atoi(kind+4):15;
 if((mrt&&renderTargets!=2&&renderTargets!=4&&renderTargets!=8)||(masked&&sampleMask!=0&&sampleMask!=1&&sampleMask!=5&&sampleMask!=15))return 1;
 if(!texture&&!vertex&&!blend&&!red&&!masked&&!mrt&&strcmp(kind,"constant"))return 1;
 struct nv_device_info device={.sm=30,.max_warps_per_mp=64,.cls_compute=0xa0c0,.cls_eng3d=0xa097};
 glsl_type_singleton_init_or_ref();struct nak_compiler*compiler=nak_compiler_create(&device);
 nir_builder b=nir_builder_init_simple_shader(vertex?MESA_SHADER_VERTEX:MESA_SHADER_FRAGMENT,nak_nir_options(compiler),"%s",kind);
 nir_def*color=NULL;
 if(texture){
  nir_def*position=nir_load_frag_coord(&b);
  nir_tex_instr*tex=nir_tex_instr_create(b.shader,read?3:2);tex->op=read?nir_texop_txf:nir_texop_tex;tex->sampler_dim=GLSL_SAMPLER_DIM_2D;tex->coord_components=2;tex->dest_type=nir_type_float32;
  // Installed driver binds fragment texture 0 as TIC 224 and sampler 1.
  // Use Kepler's documented combined bindless-handle layout (20+12 bits).
  tex->src[0]=(nir_tex_src){.src_type=nir_tex_src_texture_handle,.src=nir_src_for_ssa(nir_imm_int(&b,0x001000e0))};
  nir_def*xy=nir_channels(&b,position,3);
  if(read)xy=nir_f2u32(&b,xy);
  else {if(linear)xy=nir_fadd(&b,xy,nir_vec2(&b,nir_imm_float(&b,.25f),nir_imm_float(&b,.125f)));xy=nir_fmul(&b,xy,nir_vec2(&b,nir_imm_float(&b,1.f/64),nir_imm_float(&b,1.f/48)));}
  tex->src[1]=(nir_tex_src){.src_type=nir_tex_src_coord,.src=nir_src_for_ssa(xy)};
  if(read)tex->src[2]=(nir_tex_src){.src_type=nir_tex_src_lod,.src=nir_src_for_ssa(nir_imm_int(&b,0))};
  nir_def_init(&tex->instr,&tex->def,4,32);nir_builder_instr_insert(&b,&tex->instr);color=&tex->def;
 }else if(vertex){nir_def*id=nir_load_vertex_id(&b);nir_def*x=nir_bcsel(&b,nir_ieq_imm(&b,id,1),nir_imm_float(&b,half?1:3),nir_imm_float(&b,-1));nir_def*y=nir_bcsel(&b,nir_ieq_imm(&b,id,2),nir_imm_float(&b,3),nir_imm_float(&b,-1));color=nir_vec4(&b,x,y,nir_imm_float(&b,near?.25f:(far?.75f:.5f)),nir_imm_float(&b,1));}
 else color=nir_vec4(&b,nir_imm_float(&b,red?.875f:.25f),nir_imm_float(&b,red?.25f:.5f),nir_imm_float(&b,red?.125f:.75f),nir_imm_float(&b,blend?.5f:1.f));
 nir_store_output(&b,color,nir_imm_int(&b,0),.base=0,.write_mask=15,.src_type=nir_type_float32,.io_semantics={.location=vertex?VARYING_SLOT_POS:FRAG_RESULT_DATA0,.num_slots=1});
 b.shader->info.outputs_written=BITFIELD64_BIT(vertex?VARYING_SLOT_POS:FRAG_RESULT_DATA0);
 if(mrt)for(unsigned target=1;target<renderTargets;target++){
  nir_def*value=nir_vec4(&b,nir_imm_float(&b,(target+1)/16.f),nir_imm_float(&b,(target+3)/16.f),nir_imm_float(&b,(15-target)/16.f),nir_imm_float(&b,1));
  nir_store_output(&b,value,nir_imm_int(&b,0),.base=target,.write_mask=15,.src_type=nir_type_float32,.io_semantics={.location=FRAG_RESULT_DATA0+target,.num_slots=1});
  b.shader->info.outputs_written|=BITFIELD64_BIT(FRAG_RESULT_DATA0+target);
 }
 if(masked){nir_store_output(&b,nir_imm_int(&b,sampleMask),nir_imm_int(&b,0),.base=1,.write_mask=1,.src_type=nir_type_uint32,.io_semantics={.location=FRAG_RESULT_SAMPLE_MASK,.num_slots=1});b.shader->info.outputs_written|=BITFIELD64_BIT(FRAG_RESULT_SAMPLE_MASK);}
 nak_preprocess_nir(b.shader,compiler);const struct nak_fs_key key={0};
 struct binding_context binding={0};
 struct nak_shader_bin*bin=texture?nak_compile_shader_embedded(b.shader,true,compiler,0,&key,false,adapt_bindings,&binding):nak_compile_shader(b.shader,true,compiler,0,&key,false);
 if(texture&&(binding.failed||binding.count!=1))return 6;
 if(!bin||bin->info.sm!=30||bin->info.num_gprs>63||bin->info.slm_size||bin->info.crs_size)return 2;
 FILE*f=fopen(argv[1],"wb");if(!f)return 3;fwrite(bin->code,1,bin->code_size,f);fclose(f);
 f=fopen(argv[2],"w");if(!f)return 4;fputs(bin->asm_str,f);fclose(f);
 f=fopen(argv[3],"wb");if(!f)return 5;fwrite(bin->info.hdr,1,80,f);fclose(f);
 printf("{\"stage\":\"%s\",\"kind\":\"%s\",\"sm\":%u,\"registers\":%u,\"code_bytes\":%u,\"header_bytes\":80,\"bound_texture_slots\":%u,\"fixture_size\":[64,48],\"render_targets\":%u,\"sample_mask\":%u,\"expected_color\":[0.25,0.5,0.75,1]}\n",vertex?"vertex":"fragment",kind,bin->info.sm,bin->info.num_gprs,bin->code_size,binding.count,renderTargets,sampleMask);
 nak_shader_bin_destroy(bin);ralloc_free(b.shader);nak_compiler_destroy(compiler);glsl_type_singleton_decref();return 0;
}
