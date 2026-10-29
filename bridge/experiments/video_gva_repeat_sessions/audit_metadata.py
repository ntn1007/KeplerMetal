#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit two CPU diagnostic runs and their single-use metadata observer."""
import argparse
import hashlib
import json
import re
from pathlib import Path


def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def need(ok, why):
    if not ok: raise ValueError(why)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('base','build','metadata-build','owned-build','out'):p.add_argument('--'+n,required=True,type=Path)
    p.add_argument('--runs',required=True,nargs=2,type=Path);a=p.parse_args()
    need(not a.out.exists() and a.out.parent.is_dir(),'fresh output required')
    b=json.loads((a.build/'build.json').read_text());base=json.loads((a.base/'inputs.json').read_text())
    md=json.loads((a.metadata_build/'inputs.json').read_text()); owned=json.loads((a.owned_build/'inputs.json').read_text())
    need(b['repeat_variant'] and b['base_inputs_sha256']==sha(a.base/'inputs.json'), 'build mismatch')
    for name,digest in b['frozen'].items():need(sha(a.build/name)==digest,'build file differs')
    for name in ('video_registry_metadata_decoder.mm','video_registry_decoder.mm','video_va_vt_client.mm',
                 'video_engine_probe.mm','video_registry_observer.h','video_registry_metadata.h'):
        need(sha(a.metadata_build/name)==md['source_hashes'][name], 'metadata source differs: '+name)
    src=a.owned_build/'video_registry_metadata.mm'
    need(sha(src)==owned['source_hashes']['video_registry_metadata.mm'] and
         sha(a.owned_build/'libVideoRegistryMetadata.dylib')==owned['metadata_library_SHA256'], 'owned metadata differs')
    source=src.read_text()
    need('if(!matching||!description||configured.exchange(true))return false;' in source and
         'sites[0]=matching;sites[1]=description;enabled.store(true,std::memory_order_release);return true;' in source,
         'metadata one-shot guard differs')
    wrapper=(a.metadata_build/'video_registry_metadata_decoder.mm').read_text()
    target='    if(!KPRegistryMetadataBegin((uintptr_t)KPRegistryOriginal(1)+27,(uintptr_t)KPRegistryOriginal(3)+27))return nil;'
    replacement='''    bool metadataBegin=KPRegistryMetadataBegin((uintptr_t)KPRegistryOriginal(1)+27,(uintptr_t)KPRegistryOriginal(3)+27);
    fprintf(stderr,"KP_METADATA_BEGIN success=%d\\n",metadataBegin?1:0);fflush(stderr);
    if(!metadataBegin)return nil;'''
    need(wrapper.count(target)==1 and (a.build/'video_registry_metadata_decoder.mm').read_text()==wrapper.replace(target,replacement) and
         sha(a.build/'video_registry_metadata_decoder.mm')==b['diagnostic_decoder_source_sha256'] and
         sha(a.build/'H264-diagnostic.o')==b['diagnostic_decoder_sha256'], 'diagnostic changes differ')
    records=[]
    for run in a.runs:
        m=json.loads((run/'manifest.json').read_text());v=json.loads((run/'stdout.json').read_text())
        log=(run/'lldb.log').read_text();err=(run/'stderr.log').read_text()
        need(m['status']=='TERMINAL_SCOPED_DEBUGGER' and m['mode']=='cpu' and m['witness']=='on' and
             m['target_exit_code']==m['debugger_exit_code']==0 and m['target_and_debugger_absent'] and
             m['reservation']['state']=='terminal' and not m['reservation']['SIGKILL_requested'] and
             not m['reservation']['authoritative_ps_status'] and m['build_sha256']==sha(a.build/'build.json') and
             m['host_sha256']==sha(run/'application')==b['frozen']['application'] and
             m['lldb_log_sha256']==sha(run/'lldb.log') and m['stdout_sha256']==sha(run/'stdout.json') and
             m['stderr_sha256']==sha(run/'stderr.log'), 'run receipt differs')
        need(v['status']=='OBSERVATION_COMPLETED' and v['additional_public_decodes']==[None] and
             v['public_decode']['output_frames']==6 and v['public_decode']['different_bytes']==0 and
             v['public_decode']['CPU_reference_bytes_compared']==691200 and
             m['decoder_status']==0 and m['output_frames']==6, 'CPU report differs')
        for i in range(6):
            x=run/'outputs'/('vt-frame-%03d.nv12'%i);y=run/'assets/fixtures/H264'/('cpu-frame-%03d.nv12'%i)
            need(sha(x)==sha(y) and y.stat().st_size==115200, 'CPU frame differs')
        markers=re.findall(r'^KP_(?:REPEAT_(?:BEGIN|END) request=\d+|METADATA_BEGIN success=\d+)$',err,re.M)
        need(markers==['KP_REPEAT_BEGIN request=1','KP_METADATA_BEGIN success=1','KP_REPEAT_END request=1',
                       'KP_REPEAT_BEGIN request=2','KP_METADATA_BEGIN success=0','KP_REPEAT_END request=2'] and
             'exited with status = 0' in log, 'diagnostic sequence differs')
        records.append({'manifest_sha256':sha(run/'manifest.json'),'stderr_sha256':sha(run/'stderr.log'),
                        'first_metadata_begin':True,'second_metadata_begin':False,
                        'first_cpu_frame_bytes_matched':691200,'second_helper_nil':True})
    need(records[0]['manifest_sha256']!=records[1]['manifest_sha256'],'duplicate runs')
    result={'status':'PASS_TWO_CPU_METADATA_DIAGNOSTICS','runs':records,'build_sha256':sha(a.build/'build.json'),
            'metadata_source_sha256':sha(src),'metadata_library_sha256':sha(a.owned_build/'libVideoRegistryMetadata.dylib'),
            'wrapper_original_sha256':sha(a.metadata_build/'video_registry_metadata_decoder.mm'),
            'auditor_sha256':sha(Path(__file__)),'second_metadata_begin_refused_before_decode':True,
            'original_failure_cause_directly_observed':False,'repeated_hardware_video_proved':False,'system_modified':False}
    with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'status':result['status'],'runs':2,'hardware_video_execution_proved':False}))


if __name__=='__main__':main()
