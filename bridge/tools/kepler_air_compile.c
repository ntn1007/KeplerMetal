/* Offline AIR -> NIR -> SM30 experiment.
 * Uses OpenNVDA's MIT-licensed reader/translator and Mesa's NAK APIs.
 * Resource ABI is experimental and is NOT the existing macOS driver's ABI.
 * This executable neither opens a GPU nor submits GPU instructions. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "compiler/glsl_types.h"
#include "compiler/nir/nir.h"
#include "compiler/nir/nir_builder.h"
#include "nak.h"
#include "nv_device_info.h"
#include "air_nir.h"
#include "metallib.h"

/* The embedding driver supplies these layouts in Mesa 26.2.4. This harness
 * rejects non-compute shaders and builds only our kernel without printf.
 * Fragment/sample/printf offsets are consequently unused, not an implemented
 * graphics or printf ABI. They must be supplied by the future GPU runtime. */
const struct nak_constant_offset_info nak_const_offsets_base = {0};
const struct nak_constant_offset_info nak_const_offsets_turing_graphics = {0};
static unsigned constant_bank;

static bool lower_constants(nir_builder *builder, nir_intrinsic_instr *instruction, void *unused) {
    (void)unused;
    if (instruction->intrinsic != nir_intrinsic_load_push_constant) return false;
    builder->cursor = nir_before_instr(&instruction->instr);
    nir_def *offset = nir_iadd_imm(builder, instruction->src[0].ssa,
                                  nir_intrinsic_base(instruction));
    nir_def *value = nir_ldc_nv(builder, instruction->def.num_components,
                               instruction->def.bit_size, nir_imm_int(builder, constant_bank), offset,
                               .align_mul = instruction->def.bit_size / 8,
                               .align_offset = 0);
    nir_def_rewrite_uses(&instruction->def, value);
    nir_instr_remove(&instruction->instr);
    return true;
}

int main(int argc, char **argv) {
    if (argc != 4 && argc != 5) {
        fprintf(stderr, "usage: kepler_air_compile INPUT.air OUTPUT.sass OUTPUT.asm [CONSTANT_BANK]\n");
        return 2;
    }
    if(argc==5){char*end=NULL;unsigned long bank=strtoul(argv[4],&end,10);if(!end||*end||bank>7)return 2;constant_bank=(unsigned)bank;}
    FILE *file = fopen(argv[1], "rb");
    if (!file) return 3;
    fseek(file, 0, SEEK_END); long length = ftell(file); rewind(file);
    if (length < 4 || length > 16 * 1024 * 1024) { fclose(file); return 4; }
    unsigned char *bytes = malloc((size_t)length);
    if (!bytes) { fclose(file); return 5; }
    size_t got = fread(bytes, 1, (size_t)length, file); fclose(file);
    if (got != (size_t)length) { free(bytes); return 6; }
    const unsigned char *bitcode = bytes; size_t bitcode_length = length;
    char error[1024] = {0}; mtllib library = {0};
    if (!memcmp(bytes, "MTLB", 4)) {
        if (mtllib_parse(bytes, length, &library, error, sizeof(error))) {
            fprintf(stderr, "%s\n", error); free(bytes); return 7;
        }
        bitcode = NULL;
        for (unsigned i = 0; i < library.nfunctions; ++i)
            if (!strcmp(library.functions[i].name, "add_buffers")) {
                bitcode = library.functions[i].bitcode;
                bitcode_length = library.functions[i].bitcode_len;
            }
        if (!bitcode) { mtllib_free(&library); free(bytes); return 8; }
    }
    air_module module = {0};
    if (air_read(bitcode, bitcode_length, &module, error, sizeof(error))) {
        fprintf(stderr, "%s\n", error); mtllib_free(&library); free(bytes); return 9;
    }
    air_function *entry = NULL;
    for (unsigned i = 0; i < module.nfunctions; ++i)
        if (!module.functions[i].is_proto && !strcmp(module.functions[i].name, "add_buffers"))
            entry = &module.functions[i];
    if (!entry) return 10;

    /* Only compiler-relevant limits; no invented hardware topology.
     * SM30 and 64 warps/SM follow GK104 and Mesa's device table. */
    struct nv_device_info device = {
        .type = NV_DEVICE_TYPE_DIS, .device_id = 0x1198,
        .device_name = "GeForce GTX 880M", .chipset_name = "GK104",
        .sm = 30, .max_warps_per_mp = 64,
        .cls_eng3d = 0xa097, .cls_compute = 0xa0c0,
        .max_smem_per_wg_kB = 48,
        .sm_smem_sizes_kB = {16, 32, 48}, .sm_smem_size_count = 3,
    };
    glsl_type_singleton_init_or_ref();
    struct nak_compiler *compiler = nak_compiler_create(&device);
    air_variant variant = {.block = {32, 1, 1}};
    air_abi abi = {0};
    nir_shader *shader = air_to_nir(&module, entry, nak_nir_options(compiler),
                                   &variant, &abi, error, sizeof(error));
    if (!shader) { fprintf(stderr, "AIR to NIR: %s\n", error); return 11; }
    if (shader->info.stage != MESA_SHADER_COMPUTE) return 12;
    NIR_PASS(_, shader, nir_lower_variable_initializers, nir_var_function_temp);
    NIR_PASS(_, shader, nir_lower_returns);
    NIR_PASS(_, shader, nir_inline_functions);
    NIR_PASS(_, shader, nir_opt_copy_prop);
    NIR_PASS(_, shader, nir_opt_constant_folding);
    NIR_PASS(_, shader, nir_opt_deref);
    nir_remove_non_entrypoints(shader);
    NIR_PASS(_, shader, nir_lower_variable_initializers, ~0);
    NIR_PASS(_, shader, nir_split_var_copies);
    NIR_PASS(_, shader, nir_split_per_member_structs);
    nak_preprocess_nir(shader, compiler);
    nir_lower_compute_system_values_options system_values = {0};
    NIR_PASS(_, shader, nir_lower_compute_system_values, &system_values);
    NIR_PASS(_, shader, nir_lower_explicit_io, nir_var_mem_push_const,
             nir_address_format_32bit_offset);
    NIR_PASS(_, shader, nir_shader_intrinsics_pass, lower_constants,
             nir_metadata_control_flow, NULL);
    NIR_PASS(_, shader, nir_opt_dce);
    NIR_PASS(_, shader, nir_remove_dead_derefs);
    NIR_PASS(_, shader, nir_lower_explicit_io, nir_var_mem_global,
             nir_address_format_64bit_global);
    struct nak_shader_bin *binary = nak_compile_shader(shader, true, compiler, 0, NULL, false);
    if (!binary || binary->info.sm != 30 || !binary->code_size || !binary->code) return 13;
    file = fopen(argv[2], "wb"); if (!file) return 14;
    size_t written = fwrite(binary->code, 1, binary->code_size, file);
    int closed = fclose(file); if (written != binary->code_size || closed) return 15;
    file = fopen(argv[3], "w"); if (!file) return 16;
    if (binary->asm_str) fputs(binary->asm_str, file);
    if (fclose(file)) return 17;
    printf("{\"sm\":%u,\"code_bytes\":%u,\"registers\":%u,\"instructions\":%u,"
           "\"local_size\":[%u,%u,%u],\"buffer_slots\":%u,\"constant_block_bytes\":%u,"
           "\"constant_buffer_index\":%u,\"scope\":\"offline AIR to NIR to SM30; no GPU execution\"}\n",
           binary->info.sm, binary->code_size, binary->info.num_gprs, binary->info.num_instrs,
           binary->info.cs.local_size[0], binary->info.cs.local_size[1], binary->info.cs.local_size[2],
           abi.nbuf, abi.push_bytes,constant_bank);
    nak_shader_bin_destroy(binary); ralloc_free(shader); nak_compiler_destroy(compiler);
    glsl_type_singleton_decref(); free(abi.cdata); free(abi.refl);
    air_free(&module); mtllib_free(&library); free(bytes);
    return 0;
}
