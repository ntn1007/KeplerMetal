#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit two original-source app builds, one bootstrap and policy refusals."""
import argparse, collections, datetime, importlib.util, json, subprocess, zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
spec=importlib.util.spec_from_file_location('prior_audit',ROOT/'bridge/experiments/apple_original_bootstrap/audit.py');prior=importlib.util.module_from_spec(spec);spec.loader.exec_module(prior)
sha,need,load,tree=prior.sha,prior.need,prior.load,prior.tree
def signed(p):subprocess.run(['codesign','--verify','--strict',str(p)],check=True,capture_output=True)
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('build','archive','sample','app-a','app-b','log-a','log-b','direct','blank','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--runs',nargs=7,type=Path,required=True);a=p.parse_args();need(not a.out.exists(),'fresh output required')
    b=load(a.build/'build.json');ar=load(a.archive/'manifest.json');need(b['status']=='PREPARED_ONLY' and not b['gpu_execution'] and ar['status']=='PASS' and not ar['GPU_execution'] and b['archive_sha256']==ar['static_library_SHA256']==sha(a.archive/'libKeplerMetal.a') and b['archive_manifest_sha256']==sha(a.archive/'manifest.json'),'archive')
    for n,h in ar['source_SHA256'].items():need(sha(a.archive/'src'/n)==sha(ROOT/'bridge/src'/n)==h,'runtime source '+n)
    for n,h in b['files_sha256'].items():need(sha(a.build/n)==h,'build file '+n)
    for n in ('bootstrap.mm','Policy.h','policy_tests.mm'):need(sha(a.build/n)==sha(HERE/n),'frozen source '+n)
    signed(a.build/'bootstrap.dylib');signed(a.build/'policy_tests');tests=load(a.build/'policy-tests.json');repeat=subprocess.run([str(a.build/'policy_tests')],capture_output=True,text=True,check=True);need(json.loads(repeat.stdout)==tests and tests['status']=='PASS' and tests['valid_selections']==3 and tests['GPU_calls']==0 and len(set(tests['refusals']))==12,'CPU policy tests')
    dep=subprocess.run(['otool','-L',str(a.build/'policy_tests')],capture_output=True,text=True,check=True).stdout;need('Metal.framework' not in dep,'CPU policy test links Metal')
    source=(HERE/'bootstrap.mm').read_text();need(source.index('if(!policyHash)')<source.index('MTLCopyAllDevices()') and 'std::exit(3)' in source,'refusal ordering')
    zpath=a.sample/'AppleSample.zip';need(sha(zpath)==b['apple_archive_sha256']=='559d91d42ba4d4adff9517600de522d12f8fbc3270982ac6e0d0b5bfd414f311','sample archive')
    with zipfile.ZipFile(zpath) as z:
        names=[n for n in z.namelist() if not n.startswith('.git/') and n.endswith(('.m','.h','.metal','.pbxproj','.plist','.storyboard'))];need(len(names)==17 and all((a.sample/'source'/n).is_file() and (a.sample/'source'/n).read_bytes()==z.read(n) for n in names),'sample sources')
    binpath='Contents/MacOS/Indirect Command Buffers on CPU';libpath='Contents/Resources/default.metallib';sections=[]
    for tag,app,log in (('a',a.app_a,a.log_a),('b',a.app_b,a.log_b)):
        rec=b['apps'][tag];bundle=a.build/('Sample-'+tag+'.app');signed_host=a.build/('sign-'+tag)/'Indirect Command Buffers on CPU';signed(signed_host);need(sha(app/binpath)==rec['unsigned_sha256'] and sha(signed_host)==rec['signed_sha256']==sha(bundle/binpath) and sha(log)==b['logs_sha256'][tag] and tree(bundle)==rec['bundle_sha256'],'app build')
        x,y=prior.sections(app/binpath),prior.sections(signed_host);need(x==y,'signed sections differ');sections.append(x)
        need(sha(app/libpath)==sha(bundle/libpath)==sha(a.build/'shader.metallib')=='04d8d8ae6a4485d3be0262e971c365cfff1d5bb04f88f24cdbdfa0ffdee6afa2','default library')
        imports=subprocess.run(['nm','-u',str(signed_host)],capture_output=True,text=True,check=True).stdout;need('NSApplicationMain' in imports and 'KPCPUICB' not in imports and 'Kepler' not in imports,'executable imports')
    need(sections[0][('__TEXT','__text')]!=sections[1][('__TEXT','__text')] and b['apps']['a']['signed_sha256']!=b['apps']['b']['signed_sha256'],'app binaries not distinct');need('-O1' in a.log_b.read_text(errors='replace'),'optimization evidence')
    policies={tag:load(a.build/('policy-'+tag+'.json')) for tag in ('a','ab')};ha=b['apps']['a']['signed_sha256'];hb=b['apps']['b']['signed_sha256'];need(policies=={'a':{'version':1,'allowed_clients':[ha]},'ab':{'version':1,'allowed_clients':[ha,hb]}},'policy membership')
    historical=load(ROOT/'docs/apple-application-icb-validation.json');controls=[]
    for path,mode in ((a.direct,'direct'),(a.blank,'blank')):
        m=load(path/'manifest.json');r=load(path/'stdout.json');f=(path/'outputs/frame-0.bin').read_bytes();valid=[x for x in historical['runs'] if x['mode']==mode]
        need(sha(path/'manifest.json') in {x['manifest_sha256'] for x in valid} and m['stdout_sha256']==sha(path/'stdout.json') and m['exit_code']==0 and r['status']=='PASS' and r['mode']==mode and r['actual_apple_renderer'] and r['application_modified'],'archived control')
        need(len(f)==12800 and f[:256]==f[-256:]==bytes([0xa5])*256 and prior.sha_bytes(f[256:-256]) in {x['image_sha256'][0] for x in valid},'control pixels');controls.append(f)
    need(controls[0]!=controls[1],'blank control identical')
    order=[('a','a','normal'),('a','ab','normal'),('b','ab','normal'),('a','ab','normal'),('b','ab','normal'),('b','a','denied-client'),('a','ab','wrong-policy-hash')];intervals=[];rows=[];counts=[(i+3 if i<8 else i*3)*12 for i in range(15)]
    for path,(tag,policy,case) in zip(a.runs,order):
        m=load(path/'manifest.json');lease=m['reservation'];expected=0 if case=='normal' else 3;sel=a.build/('policy-'+policy+'.json')
        need(m['status']=='TERMINAL' and (m['client'],m['policy'],m['case'])==(tag,policy,case) and m['exit_code']==expected and m['build_sha256']==sha(a.build/'build.json') and m['runner_sha256']==sha(HERE/'experiment.py') and m['host_sha256']==b['apps'][tag]['signed_sha256'] and m['policy_sha256']==sha(sel) and m['bootstrap_sha256']==sha(a.build/'bootstrap.dylib') and m['system_before']==m['system_after']==b['system'] and m['stdout_sha256']==sha(path/'stdout.log') and m['stderr_sha256']==sha(path/'stderr.log') and tree(path/'Sample.app')==b['apps'][tag]['bundle_sha256'],'run provenance')
        need(lease['state']=='terminal' and lease['child_PID']==m['pid'] and lease['exit_code']==expected and lease['child_birth_observed'] and lease['lock_inherited_by_child'] and not lease['SIGKILL_requested'] and not lease['authoritative_ps_status'],'reservation')
        intervals.append((datetime.datetime.fromisoformat(m['started_at']),datetime.datetime.fromisoformat(m['completed_at'])));row={'client':tag,'policy':policy,'case':case,'manifest_sha256':sha(path/'manifest.json')}
        if case=='normal':
            need(m['expected_policy_sha256']==sha(sel) and m['report_sha256']==sha(path/'report.json') and m['frame_sha256']==sha(path/'frame.bin'),'capture provenance');r=load(path/'report.json');f=(path/'frame.bin').read_bytes()
            need(r['device']=='NVIDIA GeForce GTX 880M' and r['registry_id'] and not r['family_mac2'] and r['view_found'] and r['window_visible'] and r['pixel_readback'] and r['guards_intact'] and r['fence_status']==4 and r['captured_command_status']==4 and r['draw_events']==1 and not r['shader_substitution'] and r['pipeline_replacement'] and r['default_library_byte_matched'] and r['client_SHA256']==m['host_sha256'] and r['policy_SHA256']==sha(sel),'application result')
            ev=collections.Counter(x['operation'] for x in r['events']);need(ev['newIndirectCommandBuffer']==1 and ev['execute_CPU_render_ICB']==1 and ev['materialize_CPU_render_command']==15,'events');e=next(x for x in r['events'] if x['operation']=='execute_CPU_render_ICB');seq=e['evidence']['sequence_records'];need(e['executed_indices']==list(range(15)) and e['evidence']['raw_records_copied']==15 and len(seq)==15,'draw sequence')
            for i,item in enumerate(seq):
                x=item['record'];need(x['name']=='apple_explicit_view' and x['library_SHA256']==b['files_sha256']['shader.metallib'] and x['manifest_SHA256']==b['files_sha256']['profiles.json'] and x['vertex_count']==counts[i] and x['base_instance']==i and x['instances']==1 and len(x['bindings'])==3,'draw record')
            need(f==controls[0] and f!=controls[1],'frame mismatch');row['frame_sha256']=sha(path/'frame.bin')
        else:
            text=(path/'stderr.log').read_text();need(not m['report_sha256'] and not m['frame_sha256'] and not (path/'report.json').exists() and not (path/'frame.bin').exists() and 'KM_APP policy refused before device discovery' in text and 'KM_APP scoped adaptation enabled' not in text,'refusal evidence')
            if case=='denied-client':need(hb not in policies['a']['allowed_clients'] and m['expected_policy_sha256']==sha(sel),'denied client')
            else:need(m['expected_policy_sha256']=='0'*64 and m['expected_policy_sha256']!=sha(sel),'wrong policy digest')
        rows.append(row)
    intervals.sort();need(all(intervals[i][1]<=intervals[i+1][0] for i in range(6)),'overlapping processes')
    result={'status':'PASS_SCOPED_APP_POLICY','apple_archive_sha256':sha(zpath),'source_files_matched_to_archive':len(names),'client_a_sha256':ha,'client_b_sha256':hb,'different_x86_64_text_sections':True,'matching_signed_sections_per_client':[len(x) for x in sections],'bootstrap_sha256':sha(a.build/'bootstrap.dylib'),'policy_a_sha256':sha(a.build/'policy-a.json'),'policy_ab_sha256':sha(a.build/'policy-ab.json'),'runtime_sha256':ar['static_library_SHA256'],'policy_unit_refusals':12,'successful_render_processes':5,'draws_per_process':15,'pixels_per_process':3072,'frames_equal_direct_reference':True,'blank_control_differs':True,'refusal_processes':2,'refusal_before_bootstrap_device_discovery':True,'two_builds_same_apple_sample':True,'independent_third_party_apps':False,'policy_is_independent_authority':False,'pipeline_replacement':True,'process_local_injection':True,'transparent_system_integration':False,'performance_benchmark':False,'system_hashes_unchanged':True,'runs':rows};a.out.write_text(json.dumps(result,indent=2,sort_keys=True)+'\n');print(json.dumps({'status':result['status'],'render_processes':5,'refusal_processes':2}))
if __name__=='__main__':main()
