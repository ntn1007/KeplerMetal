#pragma once
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
typedef struct KBContext KBContext;
typedef struct {
 uint64_t registry_id;
 uint32_t pci_vendor,pci_device;
 uint32_t opened_client_mask;
 uint64_t shared_device_bytes,shared_resource_bytes;
 uint32_t native_submission_supported;
} KBInfo;
KBContext* kb_open(KBInfo* info);
int kb_submit_native(KBContext* context,const uint32_t* words,uint32_t count);
void kb_close(KBContext* context);
// The packet submission ABI is not yet established. No packets are sent here.
#define KB_NATIVE_SUBMISSION_NOT_IMPLEMENTED 1001
#ifdef __cplusplus
}
#endif
