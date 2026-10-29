#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit original Apple application at eight extents and bounded regressions."""
import argparse, collections, datetime, importlib.util, json, subprocess, zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
prior=module('prior_original_audit',ROOT/'bridge/experiments/apple_original_bootstrap/audit.py');stage=module('prior_stagein_audit',ROOT/'bridge/experiments/standalone_inherited_pipeline/audit.py')
sha,need,load,tree=prior.sha,prior.need,prior.load,prior.tree
EXTENTS=[(1,1),(3,7),(64,48),(127,91),(320,240),(800,600),(2560,1440),(4096,4096)]
def sign(p):subprocess.run(['codesign','--verify','--strict',str(p)],check=True,capture_output=True)
def provenance(path,build,record,report):
    m=load(path/'manifest.json');lease=m['reservation'];need(m['status']=='TERMINAL' and m['exit_code']==0 and m['build_sha256']==sha(build/'build.json') and m['system_before']==m['system_after']==record['system'] and m['stdout_sha256']==sha(path/('stdout.json' if report=='stdout.json' else 'stdout.log')) and m['stderr_sha256']==sha(path/'stderr.log'),'process provenance')
    need(lease['state']=='terminal' and lease['child_PID']==m['pid'] and lease['exit_code']==0 and lease['child_birth_observed'] and lease['lock_inherited_by_child'] and not lease['SIGKILL_requested'] and not lease['authoritative_ps_status'],'reservation');return m,(datetime.datetime.fromisoformat(m['started_at']),datetime.datetime.fromisoformat(m['completed_at']))
def frame(path,w,h):
    raw=Path(path).read_bytes();pitch=(w*4+255)&~255;need(len(raw)==512+pitch*h and raw[:256]==raw[-256:]==bytes([0xa5])*256,'frame size/guards');rows=[raw[256+i*pitch:256+(i+1)*pitch] for i in range(h)];need(all(x[w*4:]==bytes([0xa5])*(pitch-w*4) for x in rows),'row padding');return raw,prior.sha_bytes(b''.join(x[:w*4] for x in rows))
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('archive','sample','release','matrix','matrix-direct','matrix-blank','original-build','regression-build','regression','historical-direct','contract-build','contract','stage-build','stage-direct','stage-auto','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--original-runs',type=Path,nargs=2,required=True);a=p.parse_args();need(not a.out.exists(),'fresh output required')
    ar=load(a.archive/'manifest.json');need(ar['status']=='PASS' and not ar['GPU_execution'] and sha(a.archive/'libKeplerMetal.a')==ar['static_library_SHA256'],'archive')
    for n,h in ar['source_SHA256'].items():need(sha(a.archive/'src'/n)==sha(ROOT/'bridge/src'/n)==h,'runtime source '+n)
    matrix=load(a.matrix);need(matrix['status']=='PASS_APPLE_EXTENT_GRID' and matrix['archive_sha256']==ar['static_library_SHA256'] and matrix['frames']==48 and matrix['adapted_packets_checked']==240 and matrix['target_extents']==[list(x) for x in EXTENTS] and matrix['pixels_compared']==126210402 and matrix['direct_adapted_images_identical'] and matrix['row_padding_bytes_checked']==474744,'grid matrix')
    refs=[]
    for path,mode in ((a.matrix_direct,'direct'),(a.matrix_blank,'blank')):
        rows=[x for x in matrix['runs'] if x['mode']==mode and x['manifest_sha256']==sha(path/'manifest.json')];need(len(rows)==1,'grid reference manifest');images=[]
        for i,(w,h) in enumerate(EXTENTS):
            raw,digest=frame(path/'outputs'/f'frame-{i}.bin',w,h);need(digest==rows[0]['image_sha256'][i],'grid reference image');images.append(raw)
        refs.append(images)
    need(all(refs[0][i]!=refs[1][i] for i in range(2,8)),'blank controls differ for visible geometries')
    zip_path=a.sample/'AppleSample.zip';need(sha(zip_path)=='559d91d42ba4d4adff9517600de522d12f8fbc3270982ac6e0d0b5bfd414f311','sample archive')
    with zipfile.ZipFile(zip_path) as z:
        names=[n for n in z.namelist() if not n.startswith('.git/') and n.endswith(('.m','.h','.metal','.pbxproj','.plist','.storyboard'))];need(len(names)==17 and all((a.sample/'source'/n).is_file() and (a.sample/'source'/n).read_bytes()==z.read(n) for n in names),'sample sources')
    b=load(a.original_build/'build.json');rb=load(a.regression_build/'build.json');cb=load(a.contract_build/'build.json');sb=load(a.stage_build/'build.json')
    for folder,record in ((a.original_build,b),(a.regression_build,rb),(a.contract_build,cb),(a.stage_build,sb)):
        need(record['status']=='PREPARED_ONLY' and not record['gpu_execution'] and record['archive_sha256']==ar['static_library_SHA256'] and record['system']==b['system'],'build identity')
        for n,h in record['files_sha256'].items():need(sha(folder/n)==h,'build file '+n)
    for folder,record in ((a.original_build,b),(a.regression_build,rb)):
        need(tree(folder/'Sample.app')==record['bundle_files_sha256'],'build bundle');sign(folder/'application');sign(folder/'bootstrap.dylib')
    sign(a.contract_build/'contracts');sign(a.stage_build/'application');sign(a.stage_build/'bootstrap.dylib');unsigned=a.release/'Contents/MacOS/Indirect Command Buffers on CPU';need(sha(unsigned)==b['xcode_original_executable_sha256'] and sha(a.original_build/'application')==b['signed_executable_sha256'] and prior.sections(unsigned)==prior.sections(a.original_build/'application'),'original executable');need(sha(a.release/'Contents/Resources/default.metallib')==sha(a.original_build/'shader.metallib')==b['release_default_library_sha256'],'default library')
    intervals=[];rows=[];counts=[(i+3 if i<8 else i*3)*12 for i in range(15)]
    for path in a.original_runs:
        m,span=provenance(path,a.original_build,b,'report.json');intervals.append(span);r=load(path/'report.json')
        need(tree(path/'Sample.app')==b['bundle_files_sha256'] and m['host_sha256']==b['signed_executable_sha256'] and m['bootstrap_sha256']==b['files_sha256']['bootstrap.dylib'] and m['report_sha256']==sha(path/'report.json') and len(m['frames_sha256'])==8,'original run files')
        need(r['device']=='NVIDIA GeForce GTX 880M' and r['registry_id'] and not r['family_mac2'] and r['view_found'] and r['window_visible'] and r['initial_drawable_width']==800 and r['initial_drawable_height']==600 and r['initial_framebuffer_only'] and not r['window_resized_by_bootstrap'] and r['drawable_size_overridden'] and r['fence_status']==4 and r['draw_events']==8 and not r['shader_substitution'] and r['pipeline_replacement'] and r['default_library_byte_matched'] and len(r['cases'])==8,'original app observation')
        ev=collections.Counter(x['operation'] for x in r['events']);need(ev['newIndirectCommandBuffer']==1 and ev['execute_CPU_render_ICB']==8 and ev['materialize_CPU_render_command']==15,'original app events');events=[x for x in r['events'] if x['operation']=='execute_CPU_render_ICB']
        for i,(w,h) in enumerate(EXTENTS):
            case=r['cases'][i];raw,digest=frame(path/f'frame-{i}.bin',w,h);need(case['width']==w and case['height']==h and case['command_status']==4 and case['guards_intact'] and case['pixel_readback'] and m['frames_sha256'][f'frame-{i}.bin']==sha(path/f'frame-{i}.bin') and raw==refs[0][i],'original capture')
            event=events[i];seq=event['evidence']['sequence_records'];need(event['executed_indices']==list(range(15)) and event['reused_inherited_indices']==([] if i==0 else list(range(15))) and event['evidence']['raw_records_copied']==15 and len(seq)==15,'original sequence')
            for j,item in enumerate(seq):
                x=item['record'];need(x['name']=='apple_explicit_view' and x['library_SHA256']==b['files_sha256']['shader.metallib'] and x['manifest_SHA256']==b['files_sha256']['profiles.json'] and x['vertex_count']==counts[j] and x['base_instance']==j and x['instances']==1 and len(x['bindings'])==3,'original draw')
        rows.append({'manifest_sha256':sha(path/'manifest.json'),'frames_sha256':m['frames_sha256']})
    m,span=provenance(a.regression,a.regression_build,rb,'report.json');intervals.append(span);rr=load(a.regression/'report.json');oldm=load(a.historical_direct/'manifest.json');old=load(ROOT/'docs/apple-application-icb-validation.json');oldrows=[x for x in old['runs'] if x['mode']=='direct' and x['manifest_sha256']==sha(a.historical_direct/'manifest.json')];baseline=(a.historical_direct/'outputs/frame-0.bin').read_bytes();need(oldrows and oldm['exit_code']==0 and oldm['stdout_sha256']==sha(a.historical_direct/'stdout.json') and len(baseline)==12800 and baseline[:256]==baseline[-256:]==bytes([0xa5])*256 and prior.sha_bytes(baseline[256:-256])==oldrows[0]['image_sha256'][0],'historical 64 direct')
    need(tree(a.regression/'Sample.app')==rb['bundle_files_sha256'] and m['host_sha256']==rb['signed_executable_sha256'] and m['bootstrap_sha256']==rb['files_sha256']['bootstrap.dylib'] and m['report_sha256']==sha(a.regression/'report.json') and m['frame_sha256']==sha(a.regression/'frame.bin') and rr['device']=='NVIDIA GeForce GTX 880M' and not rr['family_mac2'] and rr['guards_intact'] and rr['pixel_readback'] and rr['captured_command_status']==4 and rr['draw_events']==1 and (a.regression/'frame.bin').read_bytes()==baseline,'64 regression')
    cm,span=provenance(a.contract,a.contract_build,cb,'stdout.json');intervals.append(span);cr=load(a.contract/'stdout.json');need(cm['host_sha256']==sha(a.contract/'contracts')==cb['files_sha256']['contracts'] and cr['status']=='PASS' and cr['device']=='NVIDIA GeForce GTX 880M' and cr['command_buffers_committed']==0 and not cr['GPU_execution_proved'] and cr['device_restored'],'extent contract');sign(a.contract/'contracts')
    expected={('release',1,1,80,True),('release',64,48,80,True),('release',800,600,80,True),('release',801,600,80,True),('release',800,599,80,True),('release',960,540,80,True),('release',4096,4096,80,True),('release',4097,1,80,False),('release',1,4097,80,False),('release',800,600,125,False),('old',64,48,80,True),('old',800,600,80,False)};need({(x['profile'],x['width'],x['height'],x['format'],x['accepted']) for x in cr['cases']}==expected and len(cr['cases'])==len(expected),'extent verdicts')
    stage_images=[]
    for path,mode in ((a.stage_direct,'direct'),(a.stage_auto,'auto')):
        sm,span=provenance(path,a.stage_build,sb,'stdout.json');intervals.append(span);r=load(path/'stdout.json');need(sm['mode']==mode and sm['host_sha256']==sha(path/'application')==sb['files_sha256']['application'] and sm['bootstrap_sha256']==(None if mode=='direct' else sb['files_sha256']['bootstrap.dylib']) and r['status']=='PASS' and r['device']=='NVIDIA GeForce GTX 880M' and r['mode']==('direct' if mode=='direct' else 'icb') and r['cases'][0]['completed'],'stage-in regression');sign(path/'application');stage_images.append(stage.image(path/'outputs/image.bin'))
        if mode=='auto':need(sm['events_sha256']==sha(path/'events.json') and len([x for x in load(path/'events.json') if x['operation']=='execute_CPU_render_ICB'])==3,'stage-in events')
    need(stage_images[0]==stage_images[1],'stage-in images differ');intervals.sort();need(all(intervals[i][1]<=intervals[i+1][0] for i in range(len(intervals)-1)),'audited processes overlap')
    out={'status':'PASS_APPLE_BOUNDED_EXTENTS','runtime_sha256':ar['static_library_SHA256'],'admitted_width_height':[1,4096],'tested_extents':[list(x) for x in EXTENTS],'original_processes':2,'original_frames':16,'original_initial_drawable':[800,600],'window_resized_by_bootstrap':False,'drawable_sizes_overridden':True,'framebuffer_readback_opt_in':True,'original_draws_per_frame':15,'original_images_equal_direct':True,'blank_control_differs_for_large_geometries':True,'original_source_files_checked':len(names),'matrix_sha256':sha(a.matrix),'matrix_frames':matrix['frames'],'cross_extent_cached_reuse_tested':True,'extent_contract_cases':len(expected),'contract_command_buffers_committed':0,'same_runtime_64_regression':True,'same_runtime_stagein_direct_adapted_match':True,'all_dimensions_exhaustively_tested':False,'transparent_system_integration':False,'performance_benchmark':False,'system_hashes_unchanged':True,'runs':rows};a.out.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps({'status':out['status'],'original_frames':16,'matrix_frames':48}))
if __name__=='__main__':main()
