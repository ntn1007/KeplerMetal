// SPDX-License-Identifier: MIT
// Qualified compute layout: device buffers 0/1 and a 16-byte constant buffer 2.
// This is a compiler/resource contract, not an arbitrary Metal resource ABI.
#include "KeplerResourceABI.h"

static bool local_air_address(nir_def *value, unsigned *binding, uint64_t *offset) {
    if (value->bit_size != 64 || value->num_components != 1) return false;
    nir_instr *parent = nir_def_instr(value);
    if (parent->type == nir_instr_type_intrinsic) {
        nir_intrinsic_instr *in = nir_instr_as_intrinsic(parent);
        if (in->intrinsic != nir_intrinsic_load_push_constant ||
            !nir_src_is_const(in->src[0])) return false;
        uint64_t field = nir_src_as_uint(in->src[0]) + nir_intrinsic_base(in);
        if (field >= 24 || field % 8) return false;
        *binding = (unsigned)(field / 8); *offset = 0; return true;
    }
    if (parent->type != nir_instr_type_alu) return false;
    nir_alu_instr *alu = nir_instr_as_alu(parent);
    if (alu->op != nir_op_iadd) return false;
    for (unsigned i = 0; i < 2; ++i) {
        if (!nir_src_is_const(alu->src[i].src) || alu->src[i].swizzle[0] ||
            alu->src[1-i].swizzle[0]) continue;
        if (local_air_address(alu->src[1-i].src.ssa, binding, offset)) {
            uint64_t addition = nir_src_as_uint(alu->src[i].src);
            if (addition > UINT64_MAX - *offset) return false;
            *offset += addition; return true;
        }
    }
    return false;
}

static bool lower_local_air_constants(nir_builder *b, nir_intrinsic_instr *in, void *unused) {
    (void)unused;
    if (in->intrinsic != nir_intrinsic_load_global) return false;
    unsigned binding; uint64_t offset;
    if (!local_air_address(in->src[0].ssa, &binding, &offset) || binding != 2) return false;
    unsigned bytes = in->def.num_components * in->def.bit_size / 8;
    if (!bytes || in->def.bit_size < 8 || offset > 16 || bytes > 16-offset ||
        offset % (in->def.bit_size/8)) {
        fprintf(stderr, "Constant buffer 2 exceeds the qualified 16-byte layout\n"); exit(20);
    }
    b->cursor = nir_before_instr(&in->instr);
    nir_def *v = nir_ldc_nv(b, in->def.num_components, in->def.bit_size,
                           nir_imm_int(b, KP_UNIFORM_CB), nir_imm_int(b, (unsigned)offset),
                           .align_mul=in->def.bit_size/8);
    nir_def_rewrite_uses(&in->def, v); nir_instr_remove(&in->instr); return true;
}

static bool lower_constants(nir_builder *b, nir_intrinsic_instr *in, void *unused) {
    (void)unused;
    if (in->intrinsic != nir_intrinsic_load_push_constant) return false;
    if (!nir_src_is_const(in->src[0]) || in->def.num_components != 1) {
        fprintf(stderr, "Local AIR ABI requires scalar static push fields\n"); exit(20);
    }
    uint64_t source = nir_src_as_uint(in->src[0]) + nir_intrinsic_base(in);
    unsigned offset;
    if (in->def.bit_size == 64 && (source == 0 || source == 8))
        offset = KPResourceAddressOffset((unsigned)(source/8));
    else if (in->def.bit_size == 32 && source >= 24 && source <= 32 && !(source%4))
        offset = KP_GRID_THREADS_OFFSET + (unsigned)source - 24;
    else if (in->def.bit_size == 32 && source >= 36 && source <= 44 && !(source%4))
        offset = KP_WORKGROUP_SIZE_OFFSET + (unsigned)source - 36;
    else {
        // A surviving buffer-2 pointer means an unhandled escape/access.
        fprintf(stderr, "Unsupported local AIR field %llu/%u\n",
                (unsigned long long)source, in->def.bit_size); exit(20);
    }
    b->cursor = nir_before_instr(&in->instr);
    nir_def *v = nir_ldc_nv(b, 1, in->def.bit_size, nir_imm_int(b,KP_RESOURCE_CB),
                           nir_imm_int(b,offset), .align_mul=in->def.bit_size/8);
    nir_def_rewrite_uses(&in->def,v); nir_instr_remove(&in->instr); return true;
}
