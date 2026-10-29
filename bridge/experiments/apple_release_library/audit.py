#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Re-audit the default-library ICB application, regression and contracts."""
import argparse, collections, datetime, hashlib, importlib.util, json, subprocess, zipfile
from pathlib import Path

HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[2]
spec=importlib.util.spec_from_file_location('old_original_audit',ROOT/'bridge/experiments/apple_original_bootstrap/audit.py'); old=importlib.util.module_from_spec(spec); spec.loader.exec_module(old)
sha=old.sha; need=old.need; load=old.load; tree=old.tree
def signed(p): subprocess.run(['codesign','--verify','--strict',str(p)],check=True,capture_output=True)
def provenance(path,build,record,report_file):
    m=load(path/'manifest.json'); lease=m['reservation']; need(m['status']=='TERMINAL' and m['exit_code']==0 and m['build_sha256']==sha(build/'build.json') and m['system_before']==m['system_after']==record['system'] and m['stderr_sha256']==sha(path/'stderr.log') and m.get('stdout_sha256')==sha(path/('stdout.log' if report_file=='report.json' else 'stdout.json')),'process provenance')
    need(lease['state']=='terminal' and lease['child_PID']==m['pid'] and lease['exit_code']==0 and lease['child_birth_observed'] and lease['lock_inherited_by_child'] and not lease['SIGKILL_requested'] and not lease['authoritative_ps_status'],'reservation')
    return m,(datetime.datetime.fromisoformat(m['started_at']),datetime.datetime.fromisoformat(m['completed_at']))
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('sample','release','archive','build','regression-build','regression','contract-build','contract','direct','blank','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--runs',nargs=2,type=Path,required=True);a=p.parse_args();need(not a.out.exists(),'fresh output required')
    b=load(a.build/'build.json'); rb=load(a.regression_build/'build.json'); cb=load(a.contract_build/'build.json'); ar=load(a.archive/'manifest.json');
    need(ar['status']=='PASS' and not ar['GPU_execution'] and sha(a.archive/'libKeplerMetal.a')==ar['static_library_SHA256']==b['archive_sha256']==rb['archive_sha256']==cb['archive_sha256'],'runtime identity')
    for n,h in ar['source_SHA256'].items():need(sha(a.archive/'src'/n)==sha(ROOT/'bridge/src'/n)==h,'runtime source differs '+n)
    for d,rec in ((a.build,b),(a.regression_build,rb),(a.contract_build,cb)):
        need(rec['status']=='PREPARED_ONLY' and not rec['gpu_execution'] and rec['system']==b['system'],'build profile');
        for n,h in rec['files_sha256'].items():need(sha(d/n)==h,'build artifact '+n)
    for d,rec in ((a.build,b),(a.regression_build,rb)):
        need(tree(d/'Sample.app')==rec['bundle_files_sha256'],'build bundle');signed(d/'application');signed(d/'bootstrap.dylib')
    signed(a.contract_build/'contracts');need(cb['app_build_sha256']==sha(a.build/'build.json'),'contract build')
    zpath=a.sample/'AppleSample.zip';need(sha(zpath)==b['apple_archive_sha256']=='559d91d42ba4d4adff9517600de522d12f8fbc3270982ac6e0d0b5bfd414f311','Apple archive')
    with zipfile.ZipFile(zpath) as z:
        names=[n for n in z.namelist() if not n.startswith('.git/') and n.endswith(('.m','.h','.metal','.pbxproj','.plist','.storyboard'))];need(len(names)==17 and all((a.sample/'source'/n).is_file() and (a.sample/'source'/n).read_bytes()==z.read(n) for n in names),'Apple sources differ')
    original=a.release/'Contents/MacOS/Indirect Command Buffers on CPU';need(sha(original)==b['xcode_original_executable_sha256'] and sha(a.build/'application')==b['signed_executable_sha256'],'app executable'); sections=old.sections(original);need(sections==old.sections(a.build/'application')==old.sections(a.regression_build/'application'),'app x86_64 sections differ')
    default=(a.release/'Contents/Resources/default.metallib').read_bytes();need(default==(a.build/'shader.metallib').read_bytes()==(a.build/'Sample.app/Contents/Resources/default.metallib').read_bytes() and sha(a.build/'shader.metallib')==b['release_default_library_sha256']=='04d8d8ae6a4485d3be0262e971c365cfff1d5bb04f88f24cdbdfa0ffdee6afa2','default bytes differ')
    need(sha(a.regression_build/'shader.metallib')=='adf18526f6b8fe358a30d3088dd801440b5509ac50126857174de03e17fba5bf','regression library')
    historical=load(ROOT/'docs/apple-application-icb-validation.json');controls=[]
    for path,mode in ((a.direct,'direct'),(a.blank,'blank')):
        m=load(path/'manifest.json');r=load(path/'stdout.json');f=(path/'outputs/frame-0.bin').read_bytes();valid=[x for x in historical['runs'] if x['mode']==mode]
        need(sha(path/'manifest.json') in {x['manifest_sha256'] for x in valid} and m['status']=='TERMINAL' and m['exit_code']==0 and m['stdout_sha256']==sha(path/'stdout.json') and r['status']=='PASS' and r['mode']==mode and r['application_modified'] and r['actual_apple_renderer'],'historical control')
        need(len(f)==12800 and f[:256]==f[-256:]==bytes([0xa5])*256 and hashlib.sha256(f[256:-256]).hexdigest() in {x['image_sha256'][0] for x in valid},'historical frame');controls.append(f)
    need(controls[0]!=controls[1],'blank control identical');rows=[];intervals=[];counts=[(i+3 if i<8 else i*3)*12 for i in range(15)]
    for path,build,rec,is_default in [(x,a.build,b,True) for x in a.runs]+[(a.regression,a.regression_build,rb,False)]:
        m,interval=provenance(path,build,rec,'report.json');intervals.append(interval);r=load(path/'report.json');f=(path/'frame.bin').read_bytes()
        need(tree(path/'Sample.app')==rec['bundle_files_sha256'] and m['host_sha256']==rec['signed_executable_sha256'] and m['bootstrap_sha256']==rec['files_sha256']['bootstrap.dylib'] and m['report_sha256']==sha(path/'report.json') and m['frame_sha256']==sha(path/'frame.bin'),'app artifacts')
        need(r['device']=='NVIDIA GeForce GTX 880M' and r['registry_id'] and not r['family_mac2'] and r['view_found'] and r['window_visible'] and r['pixel_readback'] and r['guards_intact'] and r['fence_status']==4 and r['captured_command_status']==4 and r['draw_events']==1 and r['shader_substitution']!=is_default,'app status')
        if is_default: need(r['default_library_byte_matched'] and r['pipeline_replacement'],'default-path evidence')
        ev=collections.Counter(x['operation'] for x in r['events']);need(ev['newIndirectCommandBuffer']==1 and ev['materialize_CPU_render_command']==15 and ev['execute_CPU_render_ICB']==1,'event counts')
        e=next(x for x in r['events'] if x['operation']=='execute_CPU_render_ICB');seq=e['evidence']['sequence_records'];need(e['executed_indices']==list(range(15)) and e['evidence']['raw_records_copied']==15 and len(seq)==15,'draw sequence')
        for i,item in enumerate(seq):
            x=item['record'];need(x['name']=='apple_explicit_view' and x['library_SHA256']==rec['files_sha256']['shader.metallib'] and x['manifest_SHA256']==rec['files_sha256']['profiles.json'] and x['vertex_count']==counts[i] and x['base_instance']==i and x['instances']==1 and len(x['bindings'])==3,'draw record')
        need(f==controls[0] and f!=controls[1],'frame mismatch');rows.append({'mode':'same_default_bytes' if is_default else 'old_library_regression','frame_sha256':sha(path/'frame.bin'),'manifest_sha256':sha(path/'manifest.json'),'report_sha256':sha(path/'report.json')})
    cm,interval=provenance(a.contract,a.contract_build,cb,'stdout.json');intervals.append(interval);cr=load(a.contract/'stdout.json');need(cm['host_sha256']==sha(a.contract/'contracts')==cb['files_sha256']['contracts'] and cr['status']=='PASS' and cr['device']=='NVIDIA GeForce GTX 880M' and cr['command_buffers_submitted']==0 and not cr['gpu_execution_proved'] and cr['release_view_accepted'] and cr['old_plain_accepted'] and cr['duplicate_refused'] and cr['device_restored'],'contract outcome')
    need({x['mutation'] for x in cr['refusals']}=={'name','color_format','depth_format','unexpected','vertex','library_hash'} and all(x['refused'] for x in cr['refusals']),'contract refusals');signed(a.contract/'contracts')
    intervals.sort();need(all(intervals[i][1]<=intervals[i+1][0] for i in range(len(intervals)-1)),'processes overlap')
    result={'status':'PASS_SAME_DEFAULT_LIBRARY','runs':rows,'contract_manifest_sha256':sha(a.contract/'manifest.json'),'runtime_sha256':ar['static_library_SHA256'],'default_library_sha256':sha(a.build/'shader.metallib'),'old_library_sha256':sha(a.regression_build/'shader.metallib'),'source_files_matched_to_archive':len(names),'matching_x86_64_sections':len(sections),'same_default_library_bytes':True,'new_pipeline_object':True,'release_assertions_disabled':True,'process_local_injection':True,'view_configuration_modified_for_capture':True,'draws_per_run':15,'pixels_per_run':3072,'frames_equal_direct_reference':True,'blank_control_differs':True,'registration_refusals':6,'duplicate_refused':True,'old_plain_accepted':True,'contract_gpu_dispatches':0,'transparent_system_integration':False,'arbitrary_shader_support':False,'performance_benchmark':False,'system_hashes_unchanged':True};a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps({'status':result['status'],'render_processes':len(rows),'refusals':6}))
if __name__=='__main__':main()
