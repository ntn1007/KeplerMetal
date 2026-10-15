// Controlled binary64 operations with the already-qualified macOS CB2 ABI.
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
static nir_def *input_address(nir_builder*b,nir_def*base,nir_def*index,unsigned slot,bool strided){
 if(!strided)return address(b,base,index,3);
 nir_def*wide=nir_iand_imm(b,nir_ushr_imm(b,constant(b,40,32),slot),1);
 return nir_iadd(b,base,nir_ishl(b,nir_u2u64(b,index),nir_iadd_imm(b,wide,3)));
}
struct norm64 {nir_def *mantissa,*exponent,*zero,*infinite,*nan,*sign;};
static nir_def *exp64(nir_builder*b,nir_def*x){return nir_iand_imm(b,nir_ushr_imm(b,nir_unpack_64_2x32_split_y(b,x),20),2047);}
static nir_def *with_exp(nir_builder*b,nir_def*x,nir_def*exponent){
 nir_def*lo=nir_unpack_64_2x32_split_x(b,x),*hi=nir_unpack_64_2x32_split_y(b,x);
 return nir_pack_64_2x32_split(b,lo,nir_ior(b,nir_iand_imm(b,hi,0x800fffff),nir_ishl_imm(b,exponent,20)));
}
static struct norm64 normalize64(nir_builder*b,nir_def*x){
 nir_def*lo=nir_unpack_64_2x32_split_x(b,x),*hi=nir_unpack_64_2x32_split_y(b,x),*e=exp64(b,x);
 nir_def*fraction=nir_ior(b,lo,nir_iand_imm(b,hi,0xfffff)),*zero=nir_iand(b,nir_ieq_imm(b,e,0),nir_ieq_imm(b,fraction,0));
 nir_def*inf=nir_iand(b,nir_ieq_imm(b,e,2047),nir_ieq_imm(b,fraction,0)),*nan=nir_iand(b,nir_ieq_imm(b,e,2047),nir_ine_imm(b,fraction,0));
 nir_def*sub=nir_iand(b,nir_ieq_imm(b,e,0),nir_inot(b,zero));
 nir_def*absolute=nir_pack_64_2x32_split(b,lo,nir_iand_imm(b,hi,0x7fffffff));
 nir_def*scaled=nir_bcsel(b,sub,nir_fmul(b,absolute,nir_imm_double(b,0x1p54)),absolute);
 nir_def*exponent=nir_isub(b,nir_iadd_imm(b,exp64(b,scaled),-1023),nir_bcsel(b,sub,nir_imm_int(b,54),nir_imm_int(b,0)));
 return (struct norm64){with_exp(b,scaled,nir_imm_int(b,1023)),exponent,zero,inf,nan,nir_iand_imm(b,hi,0x80000000)};
}
static nir_def *normalized_sqrt(nir_builder*b,nir_def*a){
 struct norm64 n=normalize64(b,a);nir_def*odd=nir_iand_imm(b,n.exponent,1),*half=nir_ishr_imm(b,n.exponent,1);
 nir_def*m=with_exp(b,n.mantissa,nir_iadd_imm(b,odd,1023));nir_def*q=nir_fsqrt(b,m);
 nir_def*result=with_exp(b,q,nir_iadd(b,exp64(b,q),half));
 result=nir_bcsel(b,n.infinite,a,result);result=nir_bcsel(b,n.zero,a,result);
 nir_def*negative=nir_iand(b,nir_ine_imm(b,n.sign,0),nir_inot(b,n.zero));
 return nir_bcsel(b,nir_ior(b,n.nan,negative),nir_imm_int64(b,0x7ff8000000000000),result);
}
static nir_def *normalized_div(nir_builder*b,nir_def*a,nir_def*d){
 struct norm64 na=normalize64(b,a),nb=normalize64(b,d);nir_def*reciprocal=nir_frcp(b,nb.mantissa);
 nir_def*q=nir_fmul(b,na.mantissa,reciprocal);
 for(unsigned i=0;i<2;i++){nir_def*r=nir_ffma(b,nir_fneg(b,q),nb.mantissa,na.mantissa);q=nir_ffma(b,r,reciprocal,q);}
 nir_def*residual=nir_ffma(b,nir_fneg(b,q),nb.mantissa,na.mantissa),*difference=nir_isub(b,na.exponent,nb.exponent);
 nir_def*targetExp=nir_iadd(b,exp64(b,q),difference),*normal=with_exp(b,q,targetExp);
 // At a subnormal midpoint, use the exact-sign FMA residual rather than
 // rounding the already rounded q again. Round-to-odd alone loses this sign
 // when just one significand bit is removed (see the preserved CPU failure).
 nir_def*shift=nir_isub(b,nir_imm_int(b,1),targetExp);
 nir_def*safeShift=nir_imin(b,nir_imax(b,shift,nir_imm_int(b,1)),nir_imm_int(b,53));
 nir_def*significand=nir_ior_imm(b,nir_iand_imm(b,q,0x000fffffffffffff),0x0010000000000000);
 nir_def*quotient=nir_ushr(b,significand,safeShift),*mask=nir_iadd_imm(b,nir_ishl(b,nir_imm_int64(b,1),safeShift),-1);
 nir_def*remainder=nir_iand(b,significand,mask),*middle=nir_ishl(b,nir_imm_int64(b,1),nir_iadd_imm(b,safeShift,-1));
 nir_def*tieUp=nir_ior(b,nir_fgt_imm(b,residual,0.0),nir_iand(b,nir_feq_imm(b,residual,0.0),nir_ine_imm(b,nir_iand_imm(b,quotient,1),0)));
 nir_def*up=nir_ior(b,nir_ult(b,middle,remainder),nir_iand(b,nir_ieq(b,remainder,middle),tieUp));
 nir_def*sub=nir_iadd(b,quotient,nir_b2i64(b,up));sub=nir_bcsel(b,nir_igt_imm(b,shift,53),nir_imm_int64(b,0),sub);
 nir_def*result=nir_bcsel(b,nir_ile_imm(b,targetExp,0),sub,normal);result=nir_bcsel(b,nir_ige_imm(b,targetExp,2047),nir_imm_int64(b,0x7ff0000000000000),result);
 nir_def*infinite=nir_ior(b,na.infinite,nb.zero),*zero=nir_ior(b,na.zero,nb.infinite);
 result=nir_bcsel(b,zero,nir_imm_int64(b,0),result);result=nir_bcsel(b,infinite,nir_imm_int64(b,0x7ff0000000000000),result);
 nir_def*lo=nir_unpack_64_2x32_split_x(b,result),*hi=nir_ior(b,nir_unpack_64_2x32_split_y(b,result),nir_ixor(b,na.sign,nb.sign));result=nir_pack_64_2x32_split(b,lo,hi);
 nir_def*nan=nir_ior(b,nir_ior(b,na.nan,nb.nan),nir_ior(b,nir_iand(b,na.zero,nb.zero),nir_iand(b,na.infinite,nb.infinite)));
 return nir_bcsel(b,nan,nir_imm_int64(b,0x7ff8000000000000),result);
}
// Explicit conversion intrinsics preserve the requested hardware rounding mode.
// Integer outputs have a defined saturating API contract, with NaN ->0. Only
// representable finite lanes execute F2I, avoiding undefined out-of-range casts.
static nir_def *reverse_conversion(nir_builder*b,nir_def*a,nir_alu_type type,nir_rounding_mode rounding){
 if(type==nir_type_float32){
  nir_def*z=nir_convert_alu_types(b,32,a,.src_type=nir_type_float64,.dest_type=type,.rounding_mode=rounding,.fp_math_ctrl=nir_fp_no_fast_math);
  return nir_u2u64(b,z);
 }
 nir_def*mag=nir_iand_imm(b,a,0x7fffffffffffffff),*negative=nir_ine_imm(b,nir_iand_imm(b,a,0x8000000000000000),0);
 bool is_signed=type==nir_type_int64;
 nir_def*limit=nir_imm_int64(b,is_signed?0x43e0000000000000:0x43f0000000000000);
 nir_def*valid=nir_ult(b,mag,limit);
 if(is_signed)valid=nir_ior(b,valid,nir_iand(b,negative,nir_ieq(b,mag,limit)));
 else valid=nir_iand(b,valid,nir_inot(b,negative));
 nir_push_if(b,valid);
 nir_def*converted=nir_convert_alu_types(b,64,a,.src_type=nir_type_float64,.dest_type=type,.rounding_mode=rounding,.fp_math_ctrl=nir_fp_no_fast_math);
 nir_push_else(b,NULL);
 nir_def*clamped=nir_bcsel(b,negative,nir_imm_int64(b,is_signed?0x8000000000000000:0),nir_imm_int64(b,is_signed?0x7fffffffffffffff:0xffffffffffffffff));
 clamped=nir_bcsel(b,nir_ult(b,nir_imm_int64(b,0x7ff0000000000000),mag),nir_imm_int64(b,0),clamped);
 nir_pop_if(b,NULL);
 return nir_if_phi(b,converted,clamped);
}
int main(int argc,char**argv){
 if(argc!=5&&argc!=6)return 1;bool strided=argc==6;if(strided&&strcmp(argv[5],"strided"))return 1;const char*kind=argv[1];unsigned local=strtoul(argv[4],NULL,10);
 bool from_i64=!strcmp(kind,"from_i64"),from_u64=!strcmp(kind,"from_u64"),from_f32=!strcmp(kind,"from_f32");
 nir_alu_type reverse_type=0;nir_rounding_mode rounding=nir_rounding_mode_undef;
 if(!strncmp(kind,"to_f32_",7))reverse_type=nir_type_float32;
 else if(!strncmp(kind,"to_i64_",7))reverse_type=nir_type_int64;
 else if(!strncmp(kind,"to_u64_",7))reverse_type=nir_type_uint64;
 if(reverse_type){
  if(!strcmp(kind+7,"rn"))rounding=nir_rounding_mode_rtne;
  else if(!strcmp(kind+7,"rz"))rounding=nir_rounding_mode_rtz;
  else if(!strcmp(kind+7,"rp"))rounding=nir_rounding_mode_ru;
  else if(!strcmp(kind+7,"rm"))rounding=nir_rounding_mode_rd;
  else return 1;
 }
 if(strcmp(kind,"add")&&strcmp(kind,"mul")&&strcmp(kind,"fma")&&strcmp(kind,"div")&&strcmp(kind,"sqrt")&&!from_i64&&!from_u64&&!from_f32&&!reverse_type)return 1;
 if(local!=32&&local!=128&&local!=1024)return 1;
 struct nv_device_info dev={.sm=30,.max_warps_per_mp=64,.cls_compute=0xa0c0,.cls_eng3d=0xa097,.max_smem_per_wg_kB=48};
 glsl_type_singleton_init_or_ref();struct nak_compiler*compiler=nak_compiler_create(&dev);
 nir_builder b=nir_builder_init_simple_shader(MESA_SHADER_COMPUTE,nak_nir_options(compiler),"fp64_%s_%u",kind,local);
 b.fp_math_ctrl=nir_fp_no_fast_math;
 b.shader->info.float_controls_execution_mode=FLOAT_CONTROLS_DENORM_PRESERVE_FP64|FLOAT_CONTROLS_ROUNDING_MODE_RTE_FP64;
 if(from_f32||reverse_type==nir_type_float32)b.shader->info.float_controls_execution_mode|=FLOAT_CONTROLS_DENORM_PRESERVE_FP32;
 b.shader->info.workgroup_size[0]=local;b.shader->info.workgroup_size[1]=1;b.shader->info.workgroup_size[2]=1;
 nir_def*lane=nir_channel(&b,nir_load_local_invocation_id(&b),0),*group=nir_channel(&b,nir_load_workgroup_id(&b),0);
 nir_def*index=nir_iadd(&b,nir_imul_imm(&b,group,local),lane),*count=constant(&b,32,32);
 nir_push_if(&b,nir_ult(&b,index,count));
 nir_def*pa=constant(&b,0,64),*pb=constant(&b,8,64),*po=constant(&b,16,64);
 nir_def*a=nir_load_global(&b,1,64,input_address(&b,pa,index,0,strided),.align_mul=8);
 nir_def*z=NULL;
 if(reverse_type)z=reverse_conversion(&b,a,reverse_type,rounding);
 else if(from_i64)z=nir_i2f64(&b,a);
 else if(from_u64)z=nir_u2f64(&b,a);
 // Binary32 lives in the low word of the existing8-byte input slot. The high
 // word is deliberately ignored, not converted or treated as binary64.
 else if(from_f32)z=nir_f2f64(&b,nir_u2u32(&b,a));
 else if(!strcmp(kind,"sqrt"))z=normalized_sqrt(&b,a);
 else{
  nir_def*c=nir_load_global(&b,1,64,input_address(&b,pb,index,1,strided),.align_mul=8);
  if(!strcmp(kind,"add"))z=nir_fadd(&b,a,c);
  else if(!strcmp(kind,"mul"))z=nir_fmul(&b,a,c);
  else if(!strcmp(kind,"div"))z=normalized_div(&b,a,c);
  else {nir_def*pc=constant(&b,24,64),*d=nir_load_global(&b,1,64,input_address(&b,pc,index,2,strided),.align_mul=8);z=nir_ffma(&b,a,c,d);}
 }
 nir_def*output=address(&b,po,index,4);
 nir_store_global(&b,z,output,.align_mul=8);
 nir_store_global(&b,index,nir_iadd_imm(&b,output,8),.align_mul=4);
 nir_store_global(&b,constant(&b,36,32),nir_iadd_imm(&b,output,12),.align_mul=4);
 nir_pop_if(&b,NULL);
 NIR_PASS(_,b.shader,nir_lower_vars_to_ssa);NIR_PASS(_,b.shader,nir_lower_doubles,NULL,nir_lower_dsqrt);nak_preprocess_nir(b.shader,compiler);
 nir_lower_compute_system_values_options options={0};NIR_PASS(_,b.shader,nir_lower_compute_system_values,&options);
 struct nak_shader_bin*bin=nak_compile_shader(b.shader,true,compiler,0,NULL,false);
 if(!bin||bin->info.sm!=30||bin->info.num_gprs>63||bin->info.slm_size||bin->info.crs_size)return 2;
 FILE*f=fopen(argv[2],"wb");if(!f)return 3;size_t n=fwrite(bin->code,1,bin->code_size,f);if(fclose(f)||n!=bin->code_size)return 3;
 f=fopen(argv[3],"w");if(!f)return 4;if(bin->asm_str)fputs(bin->asm_str,f);if(fclose(f))return 4;
 printf("{\"operation\":\"%s\",\"sm\":30,\"local\":%u,\"code_bytes\":%u,\"registers\":%u,\"scratch_bytes\":%u,\"crs_bytes\":%u,\"shared_bytes\":%u,\"strided_inputs\":%s}\n",kind,local,bin->code_size,bin->info.num_gprs,bin->info.slm_size,bin->info.crs_size,bin->info.cs.smem_size,strided?"true":"false");
 nak_shader_bin_destroy(bin);ralloc_free(b.shader);nak_compiler_destroy(compiler);glsl_type_singleton_decref();return 0;
}
