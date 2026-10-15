// Included only in an isolated AIR frontend fork, after arg()/ctx are defined.
// Public MSL compute_command calls lower to bounded portable records, not QMDs.
#include "KeplerCommandIR.h"
// The upstream AIR reader emits an unstructured CFG. Structured nir_push_if
// nodes cannot be mixed into it before nir_lower_goto_ifs.
typedef struct { nir_block *otherwise, *join; } command_branch;
static command_branch command_if(ctx *c, nir_def *condition) {
 command_branch branch={new_block(c),new_block(c)};
 nir_block *yes=new_block(c);
 nir_goto_if(&c->b,yes,condition,branch.otherwise);
 c->b.cursor=nir_after_block(yes);
 return branch;
}
static void command_else(ctx *c,command_branch branch) {
 nir_goto(&c->b,branch.join);
 c->b.cursor=nir_after_block(branch.otherwise);
}
static void command_end(ctx *c,command_branch branch,bool has_else) {
 nir_goto(&c->b,branch.join);
 if(!has_else){c->b.cursor=nir_after_block(branch.otherwise);nir_goto(&c->b,branch.join);}
 c->b.cursor=nir_after_block(branch.join);
}
static nir_def *command_word(ctx*c,nir_def*a,unsigned offset){
 return nir_load_global(&c->b,1,32,nir_iadd_imm(&c->b,a,offset),.align_mul=4);
}
static void command_store(ctx*c,nir_def*a,unsigned offset,nir_def*v){
 nir_store_global(&c->b,v,nir_iadd_imm(&c->b,a,offset),.align_mul=4);
}
static void command_flags(ctx*c,nir_def*a,nir_def*flags){
 command_store(c,a,4,nir_ior(&c->b,command_word(c,a,4),flags));
}
static void command_error(ctx*c,nir_def*a,unsigned error){
 command_store(c,a,76,nir_imm_int(&c->b,error));
 command_flags(c,a,nir_imm_int(&c->b,KP_COMMAND_FLAG_ERROR));
}
static bool lower_compute_command_ir(ctx*c,const air_inst*in,const char*name){
 bool reset=!strcmp(name,"air.reset_compute_command");
 bool pipeline=!strcmp(name,"air.set_pipeline_state_compute_command");
 bool buffer=!strcmp(name,"air.set_kernel_buffer_compute_command.p1i8")||!strcmp(name,"air.set_kernel_buffer_compute_command.p2i8");
 bool dispatch=!strcmp(name,"air.concurrent_dispatch_threadgroups_compute_command");
 bool threads=!strcmp(name,"air.concurrent_dispatch_threads_compute_command");
 bool shared=!strcmp(name,"air.set_threadgroup_memory_length_compute_command");
 bool barrier=!strcmp(name,"air.set_barrier_compute_command"),clear=!strcmp(name,"air.clear_barrier_compute_command");
 bool stage=!strcmp(name,"air.set_stage_in_region_compute_command"),copy=!strcmp(name,"air.copy_compute_command");
 if(!reset&&!pipeline&&!buffer&&!dispatch&&!shared&&!threads&&!barrier&&!clear&&!stage&&!copy)return false;
 if(!c->var->command_ir_v1){fail(c,"compute-command IR backend is disabled: %s",name);return true;}
 unsigned na=in->nops-1,expected=(reset||barrier||clear)?2:pipeline?3:buffer?5:4;
 if(na!=expected){fail(c,"compute-command arity differs: %s",name);return true;}
 if(buffer){air_value*v=&c->f->values[in->ops[4]];
  if(v->kind!=AV_CINT||v->ival!=UINT64_MAX){fail(c,"strided compute-command buffer is not supported");return true;}}
 unsigned ir_version=c->var->command_ir_v1;
 if(ir_version!=KP_COMMAND_IR_VERSION&&ir_version!=KP_COMMAND_IR_VERSION2){fail(c,"unsupported command IR version");return true;}
 c->abi->command_ir_version=ir_version;
 nir_builder*b=&c->b;nir_def*context=nir_u2u64(b,arg(c,in,0)),*index=nir_u2u32(b,arg(c,in,1));
 nir_def*capacity=command_word(c,context,8);
 nir_def*valid=nir_iand(b,nir_ieq_imm(b,command_word(c,context,0),KP_COMMAND_CONTEXT_MAGIC),nir_ieq_imm(b,command_word(c,context,4),ir_version));
 valid=nir_iand(b,valid,nir_iand(b,nir_ult(b,index,capacity),nir_ule_imm(b,capacity,KP_COMMAND_MAX_RECORDS)));
 valid=nir_iand(b,valid,nir_ieq_imm(b,command_word(c,context,24),KP_COMMAND_RECORD_BYTES));
 command_branch context_valid=command_if(c,valid);
 nir_def*base=nir_load_global(b,1,64,nir_iadd_imm(b,context,16),.align_mul=8);
 nir_def*record=nir_iadd(b,base,nir_u2u64(b,nir_imul_imm(b,index,KP_COMMAND_RECORD_BYTES)));
 if(reset){for(unsigned o=0;o<KP_COMMAND_RECORD_BYTES;o+=4)command_store(c,record,o,nir_imm_int(b,0));command_store(c,record,0,nir_imm_int(b,KP_COMMAND_RECORD_MAGIC));}
 else if(copy){
  // Cross-context descriptor compatibility needs a runtime catalogue identity;
  // this first backend accepts same-context, bounded indices only.
  nir_def*source_context=nir_u2u64(b,arg(c,in,2)),*source_index=nir_u2u32(b,arg(c,in,3));
  command_branch source_valid=command_if(c,nir_iand(b,nir_ieq(b,source_context,context),nir_ult(b,source_index,capacity)));
  nir_def*source=nir_iadd(b,base,nir_u2u64(b,nir_imul_imm(b,source_index,KP_COMMAND_RECORD_BYTES)));
  command_branch source_ready=command_if(c,nir_ieq_imm(b,command_word(c,source,0),KP_COMMAND_RECORD_MAGIC));
  for(unsigned o=0;o<KP_COMMAND_RECORD_BYTES;o+=4)command_store(c,record,o,command_word(c,source,o));
  command_else(c,source_ready);command_error(c,record,5);command_end(c,source_ready,true);
  command_else(c,source_valid);command_error(c,record,5);command_end(c,source_valid,true);
 }
 else {
  command_branch record_valid=command_if(c,nir_ieq_imm(b,command_word(c,record,0),KP_COMMAND_RECORD_MAGIC));
  if(pipeline){nir_def*token=nir_u2u64(b,arg(c,in,2)),*id=nir_u2u32(b,token),*tag=nir_u2u32(b,nir_ushr_imm(b,token,32)),*count=command_word(c,context,28);
   command_branch token_valid=command_if(c,nir_iand(b,nir_ieq_imm(b,tag,KP_COMMAND_PIPELINE_MAGIC),nir_iand(b,nir_ult(b,id,count),nir_ule_imm(b,count,KP_COMMAND_MAX_PIPELINES))));
   command_store(c,record,8,token);command_flags(c,record,nir_imm_int(b,KP_COMMAND_FLAG_PIPELINE));
   command_else(c,token_valid);command_error(c,record,1);command_end(c,token_valid,true);
  }else if(buffer){nir_def*slot=nir_u2u32(b,arg(c,in,4));
   command_branch slot_valid=command_if(c,nir_iand(b,nir_ult_imm(b,slot,ir_version==2?KP_COMMAND_V2_MAX_BINDINGS:KP_COMMAND_MAX_BINDINGS),nir_ult(b,slot,command_word(c,context,12))));
   nir_def*offset=nir_iadd_imm(b,nir_imul_imm(b,slot,8),48);
   nir_def*flag=nir_ishl(b,nir_imm_int(b,KP_COMMAND_FLAG_BUFFER0),slot);
   if(ir_version==2){offset=nir_bcsel(b,nir_ieq_imm(b,slot,3),nir_imm_int(b,104),offset);flag=nir_bcsel(b,nir_ieq_imm(b,slot,3),nir_imm_int(b,KP_COMMAND_FLAG_BUFFER3),flag);}
   nir_def*at=nir_iadd(b,record,nir_u2u64(b,offset));
   nir_store_global(b,nir_u2u64(b,arg(c,in,2)),at,.align_mul=8);command_flags(c,record,flag);
   command_else(c,slot_valid);command_error(c,record,2);command_end(c,slot_valid,true);
  }else if(dispatch||threads){nir_def*g=arg(c,in,2),*l=arg(c,in,3);if(g->num_components!=3||l->num_components!=3||g->bit_size!=32||l->bit_size!=32){fail(c,"compute-command dispatch shape differs");}
   else{for(unsigned i=0;i<3;i++){command_store(c,record,16+i*4,nir_channel(b,g,i));command_store(c,record,32+i*4,nir_channel(b,l,i));}command_store(c,record,28,nir_imm_int(b,threads?1:0));command_flags(c,record,nir_imm_int(b,KP_COMMAND_FLAG_DISPATCH));}
  }else if(shared){command_branch shared_valid=command_if(c,nir_ieq_imm(b,nir_u2u32(b,arg(c,in,3)),0));command_store(c,record,72,nir_u2u32(b,arg(c,in,2)));command_flags(c,record,nir_imm_int(b,KP_COMMAND_FLAG_SHARED));command_else(c,shared_valid);command_error(c,record,3);command_end(c,shared_valid,true);}
  else if(barrier)command_flags(c,record,nir_imm_int(b,KP_COMMAND_FLAG_BARRIER));
  else if(clear)command_store(c,record,4,nir_iand(b,command_word(c,record,4),nir_imm_int(b,~KP_COMMAND_FLAG_BARRIER)));
  else if(stage){nir_def*origin=arg(c,in,2),*size=arg(c,in,3);
   if(origin->num_components!=3||size->num_components!=3||origin->bit_size!=32||size->bit_size!=32)fail(c,"compute-command stage-in shape differs");
   else{for(unsigned i=0;i<3;i++){command_store(c,record,80+i*4,nir_channel(b,origin,i));command_store(c,record,92+i*4,nir_channel(b,size,i));}command_flags(c,record,nir_imm_int(b,KP_COMMAND_FLAG_STAGE_IN));}
  }
  command_else(c,record_valid);command_error(c,record,4);command_end(c,record_valid,true);
 }
 command_end(c,context_valid,false);return true;
}
