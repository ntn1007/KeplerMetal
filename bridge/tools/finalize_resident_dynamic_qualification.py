#!/usr/bin/env python3
"""Recheck this milestone from recorded bytes; never run GPU binaries."""
from pathlib import Path
import datetime
import hashlib
import importlib.util
import json
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/'results'
SDK=RESULTS/'resident-dynamic-sdk-build-20261014-04/KeplerMetalSDK'
OUT=RESULTS/'resident-dynamic-progress-20261014/final-qualification-03'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())


def module(name,base):
    spec=importlib.util.spec_from_file_location(name,base/(name+'.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


def main():
    OUT.mkdir(exist_ok=False)
    sys.path[:0]=[str(ROOT/'tools'),str(SDK/'examples')]
    methods={k:module(n,SDK/'examples').verify for k,n in [
        ('async','verify_cpu_icb_copy_async'),('mixed','verify_cpu_icb_copy_mixed'),
        ('graph','verify_cpu_icb_copy_graph'),('baseline','verify_cpu_icb_gpu_copy'),
        ('refusal','verify_cpu_icb_copy_refusals'),('registered','verify_registered_resident_copy'),
        ('registered_bounds','verify_registered_resident_bounds'),('reverse','verify_fp64_reverse_client'),
        ('arithmetic','verify_fp64_client'),('cas','verify_example'),('literal','verify_literal_client')]}
    dynamic=module('verify_dynamic_resident_copy',SDK/'examples').verify
    bounds=module('verify_dynamic_resident_bounds',SDK/'examples').verify
    legacy={k:module('verify_cpu_icb_'+k,ROOT/'tools').verify for k in ['manifest','grid3d']}
    checks=[];gtx=[];m1=[]

    def check(p,fn,native=False,old=False):
        if old:
            manifest=read(p/'execution/manifest.json');inp=read(p/'inputs.json')
            name='manifest'if '-manifest-'in p.name else'grid3d'
            assert sha(p/('cpu_icb_'+name+'_probe'))==inp['executable_SHA256']==manifest['original_binary_sha256']
            assert sha(p/'execution/application')==manifest['signed_binary_sha256']
            v=fn(p,portable=True)
            v.update(host_executable_SHA256_rechecked=True,portable_raw_verification_only=False,
                     signed_basename_adapter='manifest-attested SDK execution/application')
        else:v=fn(p)
        assert v['status'].startswith('PASS'),p
        checks.append({'path':str(p.relative_to(ROOT)),'verification':v})
        (m1 if native else gtx).append(p)
        return v

    positive=negative=raw_equal=0
    for mode in ['prepare','chain','range','chain_completed','range_completed','no_second']:
        p=RESULTS/('resident-dynamic-imac-'+mode+'-20261014')
        q=RESULTS/'resident-dynamic-M1-return-20261014/GPUCopyReturn/results'/mode
        a,b=check(p,dynamic),check(q,dynamic,True)
        assert a['raw_SHA256']==b['raw_SHA256'];raw_equal+=len(a['raw_SHA256'])
        if mode=='no_second':negative+=a['exact_uint32_words']
        elif mode!='prepare':positive+=a['exact_uint32_words']
    assert (positive,negative,raw_equal)==(33048,4992,144)
    guards=0
    for mode in ['prepare_bound','prepare_private','copy_bound','owner_bound','execute_owner_bound']:
        guards+=check(RESULTS/('resident-dynamic-bounds-'+mode+'-20261014'),bounds)['exact_uint32_words']
    assert guards==24960

    comparisons=[];counts={};cohorts={};fp64={}
    paths=sorted(RESULTS.glob('resident-dynamic-regression-*-20261014'));assert len(paths)==89
    old_prefix={k:'registered-resident-regression-'+k+'-'for k in ['async','mixed','graph','baseline','refusal']}
    old_prefix.update(registered='registered-resident-imac-',registered_bounds='registered-resident-bounds-')
    for p in paths:
        suffix=p.name[len('resident-dynamic-regression-'):];variant=suffix.split('-')[0]
        cohorts[variant]=cohorts.get(variant,0)+1
        v=check(p,legacy[variant]if variant in legacy else methods[variant],old=variant in legacy)
        if variant in ['reverse','arithmetic','cas','literal']:
            fp64[variant]={k:x for k,x in v.items()if k in ['exact_uint32_words','exact_fp64_words','GPU_invocations_counted','exact_f32_words']}
            continue
        if variant in legacy:
            mode='prepare'if'-prepare-'in p.name else'execute'
            if variant=='manifest':
                old=RESULTS/('cpu-icb-grid3d-dynamic-regression-'+('prepared'if mode=='prepare'else'gpu-qualified'))
                assert sha(old/'cpu_icb_manifest_probe.mm')==sha(p/'cpu_icb_manifest_probe.mm')
            else:old=RESULTS/('cpu-icb-'+variant+('-prepared'if mode=='prepare'else'-gpu-qualified'))
        else:old=RESULTS/(old_prefix[variant]+suffix[len(variant)+1:])
        count=0
        for f in sorted((p/'outputs').glob('*.bin')):
            if f.name.endswith('.commands.bin'):continue
            ref=old/'outputs'/f.name;assert f.read_bytes()==ref.read_bytes(),(f,ref)
            comparisons.append({'current':str(f.relative_to(ROOT)),'previous':str(ref.relative_to(ROOT)),'SHA256':sha(f)})
            count+=1
        counts[variant]=counts.get(variant,0)+count
    assert len(gtx)==100 and len(m1)==6 and len(checks)==106
    assert sum(counts[k]for k in ['async','mixed','graph','baseline','refusal'])==1764
    assert counts['registered']==108 and counts['registered_bounds']==48
    assert len(comparisons)==2296,counts

    history=read(RESULTS/'resident-dynamic-nonregression-suite-20261014/commands.json')
    completion=read(RESULTS/'resident-dynamic-nonregression-suite-20261014/completion.json')
    assert completion['status']=='PASS'and completion['GPU_cohorts']==89 and len(history)==107
    last={c['label']:c for c in history};assert len(last)==105 and all(x['exit_code']==0 for x in last.values())
    failed=[c for c in history if c['exit_code']!=0]
    assert [c['label']for c in failed]==['registered-prepare','manifest-prepare-verify']

    ps=subprocess.check_output(['ps','-axo','pid=,lstart=,command='],text=True)
    live={int(line.split()[0]):line for line in ps.splitlines()if line.strip()};terminals=[]
    for p in gtx+m1:
        m=read(p/'execution/manifest.json');assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']and m['GPU_reservation']['state']=='terminal'
        if p in gtx:
            now=live.get(m['pid'],'');assert not now or m['signed_executable']not in now
            state='absent'if not now else'PID_reused_by_other_command'
        else:state='remote terminal recorded and rechecked during collection'
        terminals.append({'path':str(p.relative_to(ROOT)),'PID':m['pid'],'state':state,'exit_code':0})
    build=read(SDK/'BUILD_MANIFEST.json');mf=read(SDK/'FILE_MANIFEST.json')
    for e in mf['files']:assert sha(SDK/e['path'])==e['SHA256']and(SDK/e['path']).stat().st_size==e['bytes']
    assert len(mf['files'])+1==152
    for n,h in build['source_SHA256'].items():
        f=ROOT/'src'/n
        assert sha(f if f.exists()else SDK/'src'/n)==h
    archive=SDK.parent/'KeplerMetalSDK-combined-cb0-fp64-x86_64-2026-10-14.tar.gz'
    assert sha(archive)=='6ebb8d75213cfe1030eb47317681bfa2d1ae8d24051edd654cf1b7a06c35f078'
    assert sha(SDK/'lib/libKeplerMetal.a')==build['static_library_SHA256']=='af692ec2833c3138ce3d4f639b9c6b3ffad58f8368ab1aee7ff93a8b814391d4'
    clients=read(RESULTS/'resident-dynamic-sdk-clients-20261014/client-builds.json')
    assert len(clients['builds'])==14 and clients['core_source_compilations']==0 and clients['static_library_SHA256']==build['static_library_SHA256']
    # SDK04 updates docs, packaging and the corrected oracle, while linked
    # headers/library/assets and every client build script stay identical.
    oldsdk=RESULTS/'resident-dynamic-sdk-build-20261014-02/KeplerMetalSDK'
    for folder in ['include','lib','assets']:
        for f in (oldsdk/folder).rglob('*'):
            if f.is_file():assert sha(f)==sha(SDK/f.relative_to(oldsdk))
    for f in (oldsdk/'examples').glob('build_*.py'):assert sha(f)==sha(SDK/'examples'/f.name)

    baseline=read(RESULTS/'registered-resident-progress-20261014/final-qualification/final-system-check.json')
    for e in baseline['system_files']:assert sha(e['path'])==e['sha256']
    assert len(baseline['system_files'])==83 and sha(baseline['rootpatch_path'])==baseline['rootpatch_SHA256']
    baseline.update(status='PASS',checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),system_files_unchanged=83,OCLP_rootpatch_unchanged=True)
    def save(n,v):
        with(OUT/n).open('x')as f:json.dump(v,f,indent=2,ensure_ascii=False);f.write('\n')
    save('system-check.json',baseline)
    save('terminal-process-check.json',{'status':'PASS','processes':terminals})
    save('independent-rechecks.json',{'status':'PASS','GPU_runs_started':0,'checks':checks})
    save('nonregression-raw-comparison.json',{'status':'PASS','raw_files_identical':2296,'counts':counts,'files':comparisons,'native_command_stream_bytes_not_compared':'GPU addresses differ; unchanged packet oracles validate their framing, resources and numerics'})
    receipt={'status':'PASS','date':'2026-10-14','objective_complete':False,
        'Git':{'branch':'main','commit':None,'state':'UNBORN; lab untracked'},'job_ids':[],
        'SDK_archive_SHA256':sha(archive),'static_library_SHA256':build['static_library_SHA256'],
        'core_source_SHA256':build['source_SHA256'],'SDK_files_including_manifest':152,
        'GTX_primary_cases':6,'GTX_refusal_cases':5,'GTX_nonregression_cases':89,'M1_cases':6,
        'independent_oracles_PASS':106,'positive_exact_uint32_words':positive,'negative_exact_uint32_words':negative,
        'refusal_witness_exact_uint32_words':guards,'M1_GTX_raw_files_identical':144,'nonregression_raw_files_identical':2296,
        'largest_positive_local_dynamic_pair':[1024,49152],'GTX_native_QMD_allocation_qualified':True,'M1_qualifies_NVIDIA_QMD':False,
        'same_registration_domain_required':True,'combined_static_dynamic_shared_qualified':False,
        'integration_level':2,'ordinary_applications_transparent':False,'GPU_generated_ICB':False,
        'full_ICB_contract':False,'performance_benchmark':False,'system_files_unchanged':83,'OCLP_rootpatch_unchanged':True,
        'GPU_FAILURES':[],'BLOCKED':[],
        'corrected_non_GPU_errors':['Cumulative-event count in new refusal oracle','Omitted registered launcher in SDK','Historical signed basename assumption, attested with explicit hashes'],
        'NOT_RUN':['Combined static/dynamic shared allocation','New-library performance benchmark','GPU-generated ICB','Transparent ordinary application integration'],
        'next_action':'Qualify combined static/dynamic shared allocation and wider resource layouts, then GPU-generated commands and ordinary-application integration',
        'nonregression_cohorts':cohorts,'FP64_CAS_CB0_nonregression_counts':fp64}
    save('qualification-receipt.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items()if k not in ['core_source_SHA256','nonregression_cohorts','FP64_CAS_CB0_nonregression_counts']},indent=2))


if __name__=='__main__':main()
