/* Parse our own Metal compiler output using OpenNVDA's unmodified reader.
 * This checks file/IR compatibility only; it does not execute a GPU program. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "airir.h"
#include "metallib.h"

int main(int argc, char **argv) {
    if (argc != 2) return 2;
    FILE *file = fopen(argv[1], "rb");
    if (!file) return 3;
    if (fseek(file, 0, SEEK_END)) { fclose(file); return 4; }
    long length = ftell(file);
    if (length <= 0 || length > 16 * 1024 * 1024) { fclose(file); return 4; }
    rewind(file);
    unsigned char *bytes = malloc((size_t)length);
    if (!bytes) { fclose(file); return 5; }
    size_t got = fread(bytes, 1, (size_t)length, file);
    fclose(file);
    if (got != (size_t)length) { free(bytes); return 6; }
    const unsigned char *bitcode = bytes;
    size_t bitcode_length = (size_t)length;
    mtllib library = {0};
    char error[512] = {0};
    int is_library = !memcmp(bytes, "MTLB", 4);
    if (is_library) {
        if (mtllib_parse(bytes, length, &library, error, sizeof(error))) {
            fprintf(stderr, "%s\n", error); free(bytes); return 7;
        }
        bitcode = NULL;
        for (unsigned i = 0; i < library.nfunctions; ++i) {
            if (!strcmp(library.functions[i].name, "add_buffers")) {
                bitcode = library.functions[i].bitcode;
                bitcode_length = library.functions[i].bitcode_len;
            }
        }
        if (!bitcode) { mtllib_free(&library); free(bytes); return 8; }
    }
    air_module module = {0};
    if (air_read(bitcode, bitcode_length, &module, error, sizeof(error))) {
        fprintf(stderr, "%s\n", error);
        mtllib_free(&library); free(bytes); return 9;
    }
    unsigned bodies = 0;
    for (unsigned i = 0; i < module.nfunctions; ++i)
        if (!module.functions[i].is_proto && !strcmp(module.functions[i].name, "add_buffers")) bodies++;
    printf("{\"format\":\"%s\",\"file_bytes\":%ld,\"bitcode_bytes\":%zu,"
           "\"bitcode_module_version\":%u,\"functions\":%u,\"add_buffers_bodies\":%u,"
           "\"has_air_kernel_metadata\":%s,\"scope\":\"offline parsing only\"}\n",
           is_library ? "metallib" : "AIR object", length, bitcode_length,
           module.version, module.nfunctions, bodies,
           air_named(&module, "air.kernel") ? "true" : "false");
    air_free(&module); mtllib_free(&library); free(bytes);
    return bodies == 1 ? 0 : 10;
}
