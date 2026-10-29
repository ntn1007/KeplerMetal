#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit inherited-pipeline GTX captures, records and pre-change control."""
import argparse, base64, hashlib, json, math, struct, subprocess, sys
from pathlib import Path
HERE=Path(__file__).resolve().parent; BRIDGE=HERE.parents[1]
sys.path.insert(0,str(BRIDGE/'experiments/cas_divergence'))
from run_repair import SYSTEM

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_text())
def need(ok,why):
    if not ok:raise ValueError(why)
def sign(p):need(subprocess.run(['codesign','--verify','--strict',str(p)],capture_output=True).returncode==0,'signature differs')
def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('build','archive','baseline-archive','baseline-build','baseline-direct','baseline-auto','out'):p.add_argument('--'+n,type=Path,required=True)
    p.add_argument('--runs',type=Path,nargs=4,required=True);a=p.parse_args()
    need(not a.out.exists() and a.out.parent.is_dir() and len(set(a.runs))==4,'fresh output / distinct runs')
    build=a.build.resolve();archive=a.archive.resolve();oldbuild=a.baseline_build.resolve();b=load(build/'build.json');old=load(oldbuild/'build.json');ar=load(archive/'manifest.json')
    need(b['status']==old['status']=='PREPARED_ONLY' and not b['gpu_execution'] and not old['gpu_execution'] and b['system']==old['system']==SYSTEM and b['archive_sha256']==ar['static_library_SHA256']==sha(archive/'libKeplerMetal.a') and b['archive_manifest_sha256']==sha(archive/'manifest.json'),'build provenance')
    baseline_archive=a.baseline_archive.resolve();oldar=load(baseline_archive/'manifest.json');need(old['archive_sha256']==oldar['static_library_SHA256']==sha(baseline_archive/'libKeplerMetal.a')=='9c5edae4c0bf28878d2a808e117c21472a455ff5236048f88f2f9ed9b3ad22e3' and old['archive_manifest_sha256']==sha(baseline_archive/'manifest.json'),'baseline archive')
    for name,h in oldar['source_SHA256'].items():need(sha(baseline_archive/'src'/name)==h,'baseline source differs: '+name)
    for name,h in ar['source_SHA256'].items():need(sha(archive/'src'/name)==sha(BRIDGE/'src'/name)==h,'archive source differs: '+name)
    for root,manifest in ((build,b),(oldbuild,old)):
        for n,h in manifest['files_sha256'].items():need(sha(root/n)==h,'build input differs: '+n)
        sign(root/'application');need(sha(root/'client.mm')==sha(HERE/'client.mm'),'client source differs')
    def common(root,mode,code,record,bd):
        m=load(root/'manifest.json');lease=m['reservation'];need(m['status']=='TERMINAL' and m['mode']==mode and m['exit_code']==code and m['build_sha256']==sha(bd/'build.json') and m['host_sha256']==sha(root/'application')==record['files_sha256']['application'] and m['runner_sha256']==sha(HERE/'experiment.py'),'process evidence')
        need(lease['state']=='terminal' and lease['child_PID']==m['pid'] and lease['exit_code']==code and lease['child_birth_observed'] and not lease['SIGKILL_requested'] and not lease['authoritative_ps_status'],'reservation')
        need(m['system_before']==m['system_after']==SYSTEM and m['stdout_sha256']==sha(root/'stdout.json') and m['stderr_sha256']==sha(root/'stderr.log'),'logs/system');sign(root/'application');return m
    bdirect=a.baseline_direct.resolve();bauto=a.baseline_auto.resolve();common(bdirect,'direct',0,old,oldbuild);common(bauto,'auto',1,old,oldbuild)
    need('KeplerCPUICBUnsupported: Descriptor/options outside CPU ICB profile' in (bauto/'stderr.log').read_text() and not list((bauto/'outputs').iterdir()),'baseline refusal differs')
    need(load(bdirect/'stdout.json')['status']=='PASS','baseline direct differs')
    rows=[];intervals=[];captures=[];names=('smooth','flat','smooth')
    for root,mode in zip(a.runs,('direct','auto','direct','auto')):
        root=root.resolve();m=common(root,mode,0,b,build);out=load(root/'stdout.json')
        need(m['args']==[str(build/'legacy.metallib'),str(build/'vertex.metallib'),str(build/'profiles.json'),str(root/'outputs'),mode],'arguments')
        need(out['status']=='PASS' and out['device']=='NVIDIA GeForce GTX 880M' and out['registry_id'] and out['mode']==mode and out['rejections']==(7 if mode=='auto' else 0) and [x['pipeline'] for x in out['cases']]==list(names) and all(x['completed'] and x['guard_bytes']==512 for x in out['cases']),'client report')
        events=[e for e in out['events'] if e['operation']=='execute_CPU_render_ICB'];materialized=[e for e in out['events'] if e['operation']=='materialize_CPU_render_command']
        if mode=='auto':
            need(len(events)==len(materialized)==3 and [x['record']['name'] for x in materialized]==list(names),'materialization differs')
            for event,name in zip(events,names):
                ev=event['evidence'];need(event['executed_indices']==[0] and event['caller_pipeline_restored'] and ev['raw_records_copied']==1 and ev['resource_usage_declared'] and ev['record_leases_until_completion'] and len(ev['sequence_records'])==1,'render record')
                item=ev['sequence_records'][0];meta=item['record'];packet=base64.b64decode(item['commands_base64'],validate=True)
                need(meta['name']==name and meta['vertex_count']==3 and meta['vertex_start']==1 and meta['instances']==1 and hashlib.sha256(packet).hexdigest()==meta['SHA256'] and struct.unpack('<6I',packet)==(0xa0050ea8,4,3,1,1,0),'packet differs')
        else:need(not events and not materialized,'direct control unexpectedly records ICB')
        images=[]
        for i in range(3):
            data=(root/'outputs'/f'pass-{i}.bin').read_bytes();need(len(data)==49664 and data[:256]==data[-256:]==b'\xa5'*256,'guards')
            values=struct.unpack('<12288f',data[256:-256]);need(all(math.isfinite(v) for v in values) and all(values[j]==1 for j in range(3,len(values),4)),'pixels nonfinite or alpha differs');images.append(data)
        need(images[0]==images[2] and images[0]!=images[1],'pipeline switch is not discriminating');captures.append(images);intervals.append((m['started_at'],m['completed_at']));rows.append({'mode':mode,'manifest_sha256':sha(root/'manifest.json'),'images_sha256':[hashlib.sha256(x).hexdigest() for x in images]})
    need(all(x==captures[0] for x in captures),'direct/adapted images differ')
    need(all((bdirect/'outputs'/f'pass-{i}.bin').read_bytes()==captures[0][i] for i in range(3)),'baseline images differ')
    intervals.sort();need(all(s<=e for s,e in intervals) and all(intervals[i][1]<=intervals[i+1][0] for i in range(3)),'overlap')
    result={'status':'PASS_INHERITED_PIPELINE_GPU','archive_sha256':b['archive_sha256'],'build_sha256':sha(build/'build.json'),'baseline_archive_sha256':old['archive_sha256'],'baseline_refusal_before_dispatch':True,'baseline_direct_passed':True,'processes':4,'completed_render_buffers':12,'checked_float_channels':147456,'checked_guard_bytes':6144,'expected_api_refusals':14,'pipeline_sequence':list(names),'identical_direct_adapted_raw_images':True,'distinct_pipeline_images':True,'system_files_checked_unchanged':True,'full_icb_contract':False,'transparent_system_integration':False,'performance_benchmark':False,'runs':rows}
    with a.out.open('x') as f:json.dump(result,f,indent=2,sort_keys=True);f.write('\n')
    print(json.dumps({'status':result['status'],'completed_render_buffers':12,'expected_api_refusals':14}))
if __name__=='__main__':main()
