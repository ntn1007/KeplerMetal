// Experimental compute-only ABI mapping, included by the offline C harness.
// Native resource CB1 entries retain their complete driver-managed descriptors.
// Only the pointer load is consumed here; the host must declare indirect uses.
#include "KeplerResourceABI.h"
static bool lower_constants(nir_builder *builder, nir_intrinsic_instr *instruction, void *unused) {
    (void)unused;
    if (instruction->intrinsic != nir_intrinsic_load_push_constant) return false;
    if (!nir_src_is_const(instruction->src[0]) || instruction->def.num_components != 1) {
        fprintf(stderr, "Native ABI requires scalar, statically located push fields\n"); exit(20);
    }
    uint64_t source = nir_src_as_uint(instruction->src[0]) + nir_intrinsic_base(instruction);
    unsigned bank, offset;
    if (instruction->def.bit_size == 64 && source == 0) {
        bank = KP_RESOURCE_CB; offset = KP_RESOURCE_ADDRESS_OFFSET;
    } else if (instruction->def.bit_size == 32 && source >= 8 && source <= 16 && source % 4 == 0) {
        bank = KP_RESOURCE_CB; offset = KP_GRID_THREADS_OFFSET + (unsigned)source - 8;
    } else if (instruction->def.bit_size == 32 && source >= 20 && source <= 28 && source % 4 == 0) {
        bank = KP_RESOURCE_CB; offset = KP_WORKGROUP_SIZE_OFFSET + (unsigned)source - 20;
    } else {
        fprintf(stderr, "Unsupported native ABI field %llu/%u\n", (unsigned long long)source, instruction->def.bit_size); exit(20);
    }
    builder->cursor = nir_before_instr(&instruction->instr);
    nir_def *value = nir_ldc_nv(builder, 1, instruction->def.bit_size,
                              nir_imm_int(builder, bank), nir_imm_int(builder, offset),
                              .align_mul = instruction->def.bit_size / 8, .align_offset = 0);
    nir_def_rewrite_uses(&instruction->def, value);
    nir_instr_remove(&instruction->instr);
    return true;
}
