#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU oracle for GPU-generated records, native bindings and sampled results."""
from pathlib import Path
import struct
from public_large_scratch import read,sha
from verify_local_memory import verify_device_identity
from verify_gpu_icb_texture_rows import verify_rows,verify_trace


def verify(out):
    out=Path(out);d,m,receipt=[read(out/p)for p in ['results.json','inputs.json','execution/manifest.json']]
    assert receipt['exit_code']==0 and not receipt['SIGKILL_requested']and not receipt['authoritative_ps_status']
    assert receipt['GPU_reservation']['state']=='terminal'and not receipt['GPU_reservation']['known_signed_processes_live']
    assert sha(out/'application')==receipt['original_binary_sha256']==m['executable_SHA256']
    assert sha(out/'execution/application')==receipt['signed_binary_sha256']
    for key,folder in [('source_SHA256',''),('runtime_SHA256','runtime'),('oracle_SHA256','oracles'),('assets_SHA256','')]:
        for name,digest in m[key].items():assert sha(out/folder/name)==digest,name
    verify_device_identity(d);mode=d['mode'];assert mode==m['mode']
    producer=mode!='gpu_no_producer';consumer=mode!='gpu_no_consumer';dispatch=producer and consumer
    assert d['GPU_generated_commands']is True and d['interposition']is True and d['CPU_ICB']is False
    assert d['producer_dispatches']==(3 if producer else 0)and d['materializer_dispatches']==3 and d['consumer_encoding_calls']==(3 if consumer else 0)
    assert d['user_dispatches']==(3 if dispatch else 0)
    assert d['producer_root_bytes']==40 and d['producer_library_SHA256']==m['assets_SHA256']['producer.metallib']
    assert d['library_SHA256']==m['assets_SHA256']['consumer.metallib']==read(out/'consumer-profile.json')['library_SHA256']
    verify_trace(d);proof=verify_rows(d,out/'outputs')
    return dict(status='PASS',mode=mode,GPU_dispatches=d['user_dispatches'],producer_dispatches=d['producer_dispatches'],materializer_dispatches=3,
        checked_uint32=proof['checked_uint32'],guard_bytes=proof['guard_bytes'],GPU_records_checked=proof['GPU_records_checked'],selected_banks=proof['selected_banks'],zero_CTA_records=proof['zero_CTA_records'],
        files_SHA256=proof['files_SHA256'],caller_retains_and_declares_indirect_resources=True,new_runtime_resource_lifetime_support=False,
        native_Apple_ICB_ABI=False,performance_benchmark=False)
