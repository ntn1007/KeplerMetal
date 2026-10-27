#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recheck regenerated native CAS certificates and serialized GPU witnesses."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import subprocess
import struct
from pathlib import Path
from public_large_scratch import ROOT, read, sha
from recognize_native_cas import air_contract, verify_decoder
from verify_native_cas_sdk import verify as verify_gpu


def require(condition, message):
    if not condition: raise ValueError(message)

def captured_sections(blob):
    offset=8;seen=set();sections={}
    while True:
        require(offset not in seen and 0<=offset<=len(blob)-16,'Capture linkage differs');seen.add(offset)
        nxt,kind,size=struct.unpack_from('<QII',blob,offset)
        require(size<=len(blob)-offset-16,'Capture section exceeds file')
        if kind in (0x10004,0x10005):
            require(kind not in sections,'Repeated capture section');sections[kind]=blob[offset+16:offset+16+size]
        if not nxt:break
        offset+=nxt
    require(set(sections)=={0x10004,0x10005},'Capture lacks native sections')
    return sections

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--generated',type=Path,required=True,help='Regenerated SDK preparation directory')
    p.add_argument('--build',type=Path,required=True,help='Frozen SDK client build')
    p.add_argument('--decoder',type=Path,required=True)
    p.add_argument('--final-build',type=Path,required=True)
    p.add_argument('--module-overlay',type=Path,required=True)
    p.add_argument('--runs',type=Path,nargs='+',required=True)
    a=p.parse_args();generated=a.generated.resolve();build=a.build.resolve();runs=[p.resolve() for p in a.runs]
    require(len(runs)==len(set(runs))==6,'Expected six distinct GPU host outputs')
    inputs=read(build/'inputs.json'); sdk=generated/'KeplerNativeCAS'; manifest=read(sdk/'assets/client-manifest.json')
    frozen=inputs['frozen'];require(sha(build/'client/cas_example')==inputs['executable_SHA256'],'Build client differs')
    for name,digest in frozen.items():require(sha(build/name)==digest,'Build snapshot differs: '+name)
    final=a.final_build.resolve();fi=read(final/'inputs.json')
    for name,digest in fi['frozen'].items():require(sha(final/name)==digest,'Final build snapshot differs: '+name)
    require(sha(final/'client/cas_example')==fi['executable_SHA256']==inputs['executable_SHA256'] and fi['profile']==inputs['profile'],'Final executable or profile differs')
    require({k:v for k,v in fi['frozen'].items() if k.startswith('sdk/assets/')}=={k:v for k,v in frozen.items() if k.startswith('sdk/assets/')},'Final certificate assets differ')
    member='KeplerNativeCAS.o'; objects=[]
    for path in (build/'sdk/lib/libKeplerNativeCAS.a',final/'sdk/lib/libKeplerNativeCAS.a'):
        names=subprocess.run(['xcrun','ar','-t',str(path)],capture_output=True,text=True,check=True).stdout.splitlines()
        require(names.count(member)==1 and set(names)=={'__.SYMDEF SORTED',member},'Unexpected archive members')
        objects.append(subprocess.run(['xcrun','ar','-p',str(path),member],capture_output=True,check=True).stdout)
    require(objects[0]==objects[1],'Final archive object differs from tested')
    overlay=a.module_overlay.resolve();oi=read(overlay/'inputs.json')
    require(sha(overlay/'tools/build_native_cas_sdk_module.py')==oi['source_SHA256']['tools/build_native_cas_sdk_module.py']==sha(ROOT/'tools/build_native_cas_sdk_module.py'),'Final module builder source differs')
    require(sha(sdk/'assets/cas_client.metallib')==manifest['library_SHA256']==sha(build/'sdk/assets/cas_client.metallib'),'Regenerated library differs')
    require(manifest['driver_SHA256']==inputs['profile']['system_files_SHA256']['/System/Library/Extensions/GeForceMTLDriver.bundle/Contents/MacOS/GeForceMTLDriver'],'Driver profile differs')
    names=[row['function'] for row in manifest['profiles']];require(len(names)==5 and len(set(names))==5,'Profile inventory differs')
    preparations=[]; candidate_count=0
    for row in manifest['profiles']:
        name=row['function'];cert=sdk/'assets'/row['certificate'];d=generated/('diagnosis-'+name);state=read(d/'diagnosis.json')
        require(sha(cert)==row['certificate_SHA256'] and sha(cert)==sha(build/'sdk/assets'/row['certificate']),'Certificate differs: '+name)
        c=read(cert);require(bool(c['candidate'])==bool(row['candidate'])==bool(state['candidate']),'Candidate differs')
        require(not state['GPU_dispatch'] and state['input_library_SHA256']==manifest['library_SHA256'],'Unexpected GPU work or library')
        typed=read(d/'typed-air.json');require(typed==read(d/'read-AIR-execution/execution.stdout') and air_contract(typed,name)==state['AIR'],'Captured AIR diagnosis differs')
        require(sha(d/'embedded.air')==state['embedded_AIR']['sha256'],'Embedded AIR differs')
        if row['candidate']:
            candidate_count+=1;code=(d/'native.sass').read_bytes();listing=(d/'native.asm').read_text()
            require(state['decoder_reproduced_listing'] and c['decoder_reproduced_listing'] and verify_decoder(code,listing,a.decoder),'Decoder replay differs: '+name)
            require(c['original_code_SHA256']==hashlib.sha256(code).hexdigest()==state['artifact_SHA256']['native.sass'],'Original differs')
            require(c['native_metadata_SHA256']==sha(d/'native.metadata')==state['artifact_SHA256']['native.metadata'],'Native metadata differs')
            require(c['repaired_code_SHA256']==sha(d/'repaired.sass'),'Repaired code differs')
            require(not state['native_observation']['gpu_dispatch'] and state['native_observation']['pipeline_created'],'Capture differs')
            capture=state['native_observation']['captures'];require(len(capture)==1 and capture[0]['saved'],'Compiler capture missing')
            sections=captured_sections(Path(capture[0]['file']).read_bytes())
            require(sections[0x10005]==code and sections[0x10004]==(d/'native.metadata').read_bytes(),'Compiler capture differs from certificate inputs')
        else:require(not c['decoder_reproduced_listing'] and not state['AIR']['qualified'],'Semantic negative differs')
        preparations.append({'function':name,'candidate':bool(row['candidate']),'certificate_SHA256':sha(cert)})
    require(candidate_count==4,'Candidate count differs')
    intervals=[]; signed=[]
    for path in generated.rglob('manifest.json'):
        if not path.parent.name.endswith('-execution'):continue
        m=read(path);lease=m['GPU_reservation'];require(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and lease['state']=='terminal' and not lease['known_signed_processes_live'],'Preparation process not terminal')
        require(sha(Path(m['signed_executable']))==m['signed_binary_sha256'],'Preparation binary differs')
        intervals.append((datetime.fromisoformat(m['started_at']),datetime.fromisoformat(m['completed_at'])));signed.append(m['pid'])
    require(len(signed)==21 and len(set(signed))==21,'Preparation process set differs')
    rows=[]
    for path in runs:
        i=read(path/'inputs.json');m=read(path/'execution/manifest.json');lease=m['GPU_reservation']
        require(i['build_inputs_SHA256']==sha(build/'inputs.json') and i['executable_SHA256']==inputs['executable_SHA256'],'Run build differs')
        require(i['frozen']==frozen and read(path/'results.json')==read(path/'execution/execution.stdout'),'Run snapshot or output differs')
        require(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and lease['state']=='terminal' and not lease['known_signed_processes_live'],'GPU process not terminal')
        require(sha(path/'application')==m['original_binary_sha256']==inputs['executable_SHA256'] and sha(path/'execution/application')==m['signed_binary_sha256']==lease['signed_binary_sha256'],'Run executable differs')
        for name,digest in frozen.items():
            if name.startswith('sdk/assets/'):require(sha(path/'assets'/name[len('sdk/assets/'):])==digest,'Run asset differs: '+name)
            elif name.startswith(('support/','runtime/')):require(sha(path/name)==digest,'Run support differs: '+name)
        require(m['launcher_SHA256']==frozen['runtime/run_sdk_host.py'] and m['reservation_module_SHA256']==frozen['runtime/lab_gpu_reservation.py'],'Launcher or reservation differs')
        require(m['arguments']==[str(path/'assets'),str(path/'assets/client-manifest.json'),str(path/'outputs'),i['mode']],'Host arguments differ')
        actual=verify_gpu(path);require(actual==read(path/'independent-verification.json'),'Stored verifier differs');rows.append(actual)
        intervals.append((datetime.fromisoformat(m['started_at']),datetime.fromisoformat(m['completed_at'])))
    require(Counter(r['mode'] for r in rows)==Counter({'negative':1,'prepare':1,'native':2,'execute':2}),'Run coverage differs')
    intervals.sort();require(all(x<=y for x,y in intervals) and all(x[1]<=y[0] for x,y in zip(intervals,intervals[1:])),'Host intervals overlap')
    execute=[x for x in rows if x['mode']=='execute'];native=[x for x in rows if x['mode']=='native']
    print(json.dumps({'status':'PASS','candidate_certificates':candidate_count,'semantic_negative_certificates':1,
      'preparation_signed_processes':len(signed),'GPU_hosts':len(rows),'nonoverlapping':True,
      'repaired_GPU_command_buffers':sum(x['user_GPU_command_buffers'] for x in execute),
      'repaired_and_control_CAS_operations':sum(x['correct_CAS_operations'] for x in execute),
      'repaired_and_control_uint32_words':sum(x['correct_uint32_words'] for x in execute),
      'native_defect_words_observed':sum(x['expected_native_defect_words'] for x in native),
      'negative_pre_constructor_rejections':next(x['pre_constructor_rejections'] for x in rows if x['mode']=='negative'),
      'negative_constructor_pin_rejections':next(x['constructor_pin_rejections'] for x in rows if x['mode']=='negative'),
      'GPU_archive_SHA256':inputs['SDK_archive_SHA256'],'executable_SHA256':inputs['executable_SHA256'],
      'final_archive_SHA256':fi['SDK_archive_SHA256'],'final_object_SHA256':hashlib.sha256(objects[0]).hexdigest(),
      'final_object_and_client_identical_to_GPU_tested':True,
      'decoder_SHA256':sha(a.decoder),'certificates':preparations,'installed_driver_modified':False,
      'scope':'Exact regenerated certificates and adapted client on GTX; not global compiler repair or performance'},indent=2,sort_keys=True))

if __name__=='__main__':main()
