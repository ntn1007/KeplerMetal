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
SDK=RESULTS/'gpu-generated-geometry-sdk-build-20261014-07/KeplerMetalSDK'
OUT=RESULTS/'gpu-generated-geometry-progress-20261014/final-qualification'
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
        ('arithmetic','verify_fp64_client'),('cas','verify_example'),('literal','verify_literal_client'),('dynamic','verify_dynamic_resident_copy'),('dynamic_bounds','verify_dynamic_resident_bounds'),('combined','verify_combined_shared_copy'),('combined_bounds','verify_combined_shared_bounds'),('selection','verify_gpu_command_selection'),('selection_refusals','verify_gpu_selection_refusals')]}
    dynamic=module('verify_gpu_command_geometry',SDK/'examples').verify
    bounds=module('verify_gpu_geometry_refusals',SDK/'examples').verify
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
    for mode in ['prepare','select','range','split','completed','copy','no_producer','no_selector']:
        p=RESULTS/('gpu-generated-geometry-imac-'+mode+'-20261014'+('-03'if mode=='prepare'else''))
        q=RESULTS/'gpu-generated-geometry-M1-return-20261014/GPUCopyReturn/results'/mode
        a,b=check(p,dynamic),check(q,dynamic,True)
        assert a['raw_SHA256']==b['raw_SHA256'];raw_equal+=len(a['raw_SHA256'])
        if mode in ['no_producer','no_selector']:negative+=a['exact_uint32_words']
        elif mode!='prepare':positive+=a['exact_uint32_words']
    assert (positive,negative,raw_equal)==(115988,18432,300)
    guard=check(RESULTS/'gpu-generated-geometry-refusals-20261014',bounds)
    guards=guard['exact_uint32_words'];assert guards==22528 and guard['API_refusal_checks']==60

    comparisons=[];counts={};cohorts={};fp64={}
    paths=sorted(RESULTS.glob('gpu-generated-geometry-regression-*-20261014'));assert len(paths)==120
    for p in paths:
        suffix=p.name[len('gpu-generated-geometry-regression-'):];variant=suffix.split('-')[0]
        cohorts[variant]=cohorts.get(variant,0)+1
        v=check(p,legacy[variant]if variant in legacy else methods[variant],old=variant in legacy)
        if variant in ['reverse','arithmetic','cas','literal']:
            fp64[variant]={k:x for k,x in v.items()if k in ['exact_uint32_words','exact_fp64_words','GPU_invocations_counted','exact_f32_words']}
            continue
        if variant=='selection':old=RESULTS/p.name.replace('gpu-generated-geometry-regression-selection-','gpu-generated-selection-imac-')
        elif variant=='selection_refusals':old=RESULTS/'gpu-generated-selection-refusals-20261014'
        else:old=RESULTS/p.name.replace('gpu-generated-geometry-regression-','gpu-generated-selection-regression-')
        count=0
        for f in sorted((p/'outputs').glob('*.bin')):
            if f.name.endswith('.commands.bin'):continue
            ref=old/'outputs'/f.name;assert f.read_bytes()==ref.read_bytes(),(f,ref)
            comparisons.append({'current':str(f.relative_to(ROOT)),'previous':str(ref.relative_to(ROOT)),'SHA256':sha(f)})
            count+=1
        counts[variant]=counts.get(variant,0)+count
    assert len(gtx)==129 and len(m1)==8 and len(checks)==137
    assert sum(counts[k]for k in ['async','mixed','graph','baseline','refusal'])==1764
    assert counts['registered']==108 and counts['registered_bounds']==48
    assert len(comparisons)==3253,counts

    history=read(RESULTS/'gpu-generated-geometry-nonregression-suite-20261014/commands.json')
    completion=read(RESULTS/'gpu-generated-geometry-nonregression-suite-20261014/completion.json')
    assert completion['status']=='PASS'and completion['GPU_cohorts']==120 and len(history)==167 and all(c['exit_code']==0 for c in history)

    ps=subprocess.check_output(['ps','-axo','pid=,lstart=,command='],text=True)
    live={int(line.split()[0]):line for line in ps.splitlines()if line.strip()};terminals=[]
    for p in gtx+m1:
        m=read(p/'execution/manifest.json');assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']and m['GPU_reservation']['state']=='terminal'
        if p in gtx:
            now=live.get(m['pid'],'');assert not now or m['signed_executable']not in now
            state='absent'if not now else'PID_reused_by_other_command'
        else:state='remote terminal recorded and rechecked during collection'
        terminals.append({'path':str(p.relative_to(ROOT)),'PID':m['pid'],'state':state,'exit_code':0})
    encoding_failures=[]
    for case in ['gpu-generated-geometry-imac-prepare-20261014','gpu-generated-geometry-imac-prepare-20261014-02']:
        p=RESULTS/case;m=read(p/'execution/manifest.json');assert m['exit_code']==-6 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and m['GPU_reservation']['state']=='terminal'
        assert m['signed_executable']not in live.get(m['pid'],'')
        stderr=(p/'execution/execution.stderr').read_text();assert 'Resident preparation differs; discard this command buffer' in stderr
        encoding_failures.append({'path':str(p.relative_to(ROOT)),'PID':m['pid'],'exit_code':m['exit_code'],'experimental_command_committed':False,'stderr_SHA256':sha(p/'execution/execution.stderr')})
    build=read(SDK/'BUILD_MANIFEST.json');mf=read(SDK/'FILE_MANIFEST.json')
    for e in mf['files']:assert sha(SDK/e['path'])==e['SHA256']and(SDK/e['path']).stat().st_size==e['bytes']
    assert len(mf['files'])+1==177
    for n,h in build['source_SHA256'].items():
        f=ROOT/'src'/n
        assert sha(f if f.exists()else SDK/'src'/n)==h
    archive=SDK.parent/'KeplerMetalSDK-combined-cb0-fp64-x86_64-2026-10-14.tar.gz'
    assert sha(archive)==read(SDK.parent/'delivery.json')['SHA256']
    assert sha(SDK/'lib/libKeplerMetal.a')==build['static_library_SHA256']=='e4b9461525e28a1bb05cb270fa6aaf9b1465b5761c6d2fd81d7f19057493d4d3'
    clients=read(RESULTS/'gpu-generated-geometry-sdk-clients-20261014/client-builds.json')
    assert len(clients['builds'])==21 and clients['core_source_compilations']==0 and clients['static_library_SHA256']==build['static_library_SHA256']
    # SDK03 updates documentation, while linked
    # headers/library/assets and every client build script stay identical.
    oldsdk=RESULTS/'gpu-generated-geometry-sdk-build-20261014-05/KeplerMetalSDK'
    for folder in ['include','lib','assets']:
        for f in (oldsdk/folder).rglob('*'):
            if f.is_file():assert sha(f)==sha(SDK/f.relative_to(oldsdk))
    for f in (oldsdk/'examples').glob('build_*.py'):assert sha(f)==sha(SDK/'examples'/f.name)

    baseline=read(RESULTS/'gpu-generated-selection-progress-20261014/final-qualification/system-check.json')
    for e in baseline['system_files']:assert sha(e['path'])==e['sha256']
    assert len(baseline['system_files'])==83 and sha(baseline['rootpatch_path'])==baseline['rootpatch_SHA256']
    baseline.update(status='PASS',checked_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),system_files_unchanged=83,OCLP_rootpatch_unchanged=True)
    def save(n,v):
        with(OUT/n).open('x')as f:json.dump(v,f,indent=2,ensure_ascii=False);f.write('\n')
    save('system-check.json',baseline)
    save('preserved-encoding-failures.json',{'status':'EXPECTED_GUARD_REFUSALS_RETAINED','failures':encoding_failures,'guards_relaxed':False})
    save('terminal-process-check.json',{'status':'PASS','processes':terminals})
    save('independent-rechecks.json',{'status':'PASS','GPU_runs_started':0,'checks':checks})
    save('nonregression-raw-comparison.json',{'status':'PASS','raw_files_identical':3253,'counts':counts,'files':comparisons,'native_command_stream_bytes_not_compared':'GPU addresses differ; unchanged packet oracles validate their framing, resources and numerics'})
    receipt={'status':'PASS','date':'2026-10-14','objective_complete':False,
        'Git':{'branch':'main','commit':None,'state':'UNBORN; lab untracked'},'job_ids':[],
        'SDK_archive_SHA256':sha(archive),'static_library_SHA256':build['static_library_SHA256'],
        'core_source_SHA256':build['source_SHA256'],'SDK_files_including_manifest':177,
        'GTX_primary_cases':8,'GTX_refusal_cases':1,'GTX_nonregression_cases':120,'M1_cases':8,'API_refusal_checks':60,
        'independent_oracles_PASS':137,'positive_exact_uint32_words':positive,'negative_exact_uint32_words':negative,
        'refusal_witness_exact_uint32_words':guards,'M1_GTX_raw_files_identical':300,'nonregression_raw_files_identical':3253,
        'candidate_count':3,'GPU_choice_from_Private_reduction':True,'GPU_copy_of_sealed_existing_commands':True,'GPU_generated_X_grid_prefix':True,'QMD_grid_word_offset':48,'local_size_modified':False,'geometry_library_SHA256':'f6cc04a4c2555a2555dc06a2f02687ffe5a63fb5304619b1d9662ec1f0176441','observed_group_counts':[1,3,4,5,6],
        'GTX_trusted_selector_library_SHA256':'b6d3f29fc4f85dd020f96fff3fc5f2586548aad483ea2649172b56545a9e581c',
        'M1_native_compute_command_copy_and_concurrent_dispatch_reference':True,'CPU_choice_read_before_execution':False,
        'CPU_partials_on_GPU_selected_slots_require_reset':True,'same_registration_domain_required':True,
        'integration_level':2,'ordinary_applications_transparent':False,'GPU_generated_command_selection':True,'general_GPU_ICB_encoding':False,
        'full_ICB_contract':False,'performance_benchmark':False,'system_files_unchanged':83,'OCLP_rootpatch_unchanged':True,
        'GPU_FAILURES':[],'encoding_failures_preserved':['gpu-generated-geometry-imac-prepare-20261014','gpu-generated-geometry-imac-prepare-20261014-02'],'public_clients_compiled_without_core_sources':21,'BLOCKED':[],
        'corrected_non_GPU_errors':['Fixture respects existing max_invocations4096; local1024 has at most4 groups','Geometry limits use device const to avoid additional constant bank; primer equality unchanged','Refusal status label clarified without another GPU run'],
        'NOT_RUN':['Arbitrary GPU command construction and general MSL ICB frontend beyond certified X-grid prefix','New-library performance benchmark','Transparent ordinary application integration','Broader resource layouts'],
        'next_action':'Generalize certified command state construction and qualify supported application integration; retain full hardware objective',
        'nonregression_cohorts':cohorts,'FP64_CAS_CB0_nonregression_counts':fp64}
    save('qualification-receipt.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items()if k not in ['core_source_SHA256','nonregression_cohorts','FP64_CAS_CB0_nonregression_counts']},indent=2))


if __name__=='__main__':main()
