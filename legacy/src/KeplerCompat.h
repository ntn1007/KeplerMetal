#pragma once
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef struct KCContext KCContext;
KCContext* kc_create(uint32_t rows,uint32_t columns);
const char* kc_device_name(KCContext* context);
int kc_softmax(KCContext* context,const float* input,float* output,double* gpu_seconds);
int kc_upload(KCContext* context,const float* input);
int kc_run_resident(KCContext* context,double* gpu_seconds);
int kc_download(KCContext* context,float* output);
void kc_destroy(KCContext* context);
#ifdef __cplusplus
}
#endif
