#!/usr/bin/env python3
"""Audit bounded native allocation thresholds and new104/120 programs, offline."""
from pathlib import Path
import argparse
import json

from analyze_native_control_reserve import analyze
from build_control_flow_probe import source as native_source
from qualify_native_reserve import verify_case, under_results
from verify_native_control_reserve import load, sha, require, unchanged_failure, observations
from verify_native_reserve_sweep import verify as sweep
from verify_native_allocation_runtime import matrix

ROOT = Path(__file__).resolve().parents[1]
PROGRESS = ROOT / 'results/native-allocation-rule-progress-20261016'
NATIVE = ROOT / 'results/native-control-generalization-build-20261016'
OBS = ROOT / 'results/native-control-generalization-observations-20261016'
LAB = ROOT / 'results/native-allocation-runtime-build-20261016-04'
PUBLIC = ROOT.parents[1] / 'publication/KeplerMetal/build/native-allocation-public-20261016'


def audit_sweep(row, native, obs):
    proof = sweep(under_results(row['result']), under_results(row['build']), native, obs,
                  row['reserve'], row['depth'])
    stored = load(under_results(row['result']) / 'independent-verification.json')
    require(proof == stored, 'sweep result changed')
    require(row['execution_exit_code'] == 0 and proof['numerical_status'] == row['numerical_status'], 'sweep process/outcome')
    proof.pop('files_SHA256'); return {'result': row['result'], **proof}


def verify():
    start = load(PROGRESS / 'start.json')
    require(start['previous_goal_turn_classification'] == 'progress'
            and start['base_commit'] == 'a93c44f5caa4a2f4c6e024ad266ef5d2b1e755c2', 'turn provenance')
    for n, h in start['runtime_before_SHA256'].items():
        require(sha(ROOT / 'src' / n) == h, 'common runtime modified')
    require(sha(ROOT / 'tools/NativeControlReserveExperiment.mm') == start['standalone_before_SHA256']
            == 'ecff9c4f83d25283cf35a31ac77f53bcc9d1032a77b21209aba07ce3c5795991', 'experiment modified')
    for lib in [LAB, PUBLIC]:
        m = load(lib / 'manifest.json')
        require(sha(lib / 'libKeplerMetal.a') == m['static_library_SHA256'], 'archive changed')
        for n, h in m['source_SHA256'].items():
            relative = n if n.startswith('src/') else 'src/' + n
            require(sha(lib / relative) == h and sha(ROOT / relative) == h, 'runtime source snapshot')
    ni = load(NATIVE / 'inputs.json')
    require(ni['depths'] == [104,120] and ni['variant'] == 'nested' and not ni['entry_witness']
            and (NATIVE / 'control_flow.metal').read_text() == native_source(False,[104,120],'nested'), 'new source generation')
    for n, h in ni['source_hashes'].items(): require(sha(NATIVE / n) == h, 'new source hash')
    for n, h in ni['assets_SHA256'].items(): require(sha(NATIVE / 'assets' / n) == h, 'new library hash')
    od=load(OBS/'observations.json')
    require(od['native_build_inputs_SHA256']==sha(NATIVE/'inputs.json')
            and ni['capture_executable_SHA256']==sha(NATIVE/'compiler_output_trace'),'capture build provenance')
    for row in od['records']:
        folder=OBS/row['function'];m=load(folder/'execution/manifest.json')
        raw=load(folder/'execution/execution.stdout');signed=Path(m['signed_executable']).resolve()
        signed.relative_to(folder.resolve()/'execution')
        require(m['original_binary_sha256']==ni['capture_executable_SHA256']
                and m['signed_binary_sha256']==sha(signed)
                and m['GPU_reservation']['state']=='terminal'
                and m['GPU_reservation']['lock_inherited_by_child']
                and raw['pipeline_created'] and not raw['gpu_dispatch']
                and len(raw['captures'])==1,'native observer process')
    native_observations = observations(OBS)
    require(len(native_observations) == 2, 'new native observations')
    static = load(PROGRESS / 'static-control-analysis.json')
    folders = sorted({r['observation_file'].rsplit('/',1)[0] for r in static['records']})
    recomputed = [row for folder in folders for row in analyze(ROOT / folder)]
    require(sorted(recomputed,key=lambda r:(r['observation_file'],r['function']))
            == sorted(static['records'],key=lambda r:(r['observation_file'],r['function']))
            and static['profiles'] == 25, 'static byte/listing identity')
    new_static = analyze(OBS)
    require(new_static == load(PROGRESS / 'new-program-static-analysis.json')['records'], 'new static analysis')
    for n, h in load(PROGRESS / 'source-pins.json').items(): require(sha(ROOT / n) == h, 'open source pin')
    require(load(PROGRESS / 'CRS-function-origin.json')['CRS_function_identical_to_archive'], 'Mesa CRS origin')
    checked = []
    for row in load(PROGRESS / 'intermediate-history.json'):
        native = under_results(row['native']); obs = under_results(row['observations'])
        checked.append(audit_sweep(row,native,obs))
    baseline = []
    for row in load(PROGRESS / 'generalization-history.json'):
        if row['reserve'] is None:
            proof = unchanged_failure(under_results(row['result']),row['depth'],under_results(row['build']))
            require(proof == load(under_results(row['result'])/'independent-verification.json')
                    and row['numerical_status'] == 'FAIL', 'native baseline result')
            baseline.append({'result':row['result'],'depth':row['depth'],**proof})
        else: checked.append(audit_sweep(row,NATIVE,OBS))
    for row in load(PROGRESS / 'new-lower-controls-history.json'):
        checked.append(audit_sweep(row,NATIVE,OBS))
    require(len(checked)==8 and len(baseline)==2, 'new experiment completeness')
    positives=[r for r in checked if r['numerical_status']=='PASS']
    failures=[r for r in checked if r['numerical_status']=='FAIL']
    require(len(positives)==6 and len(failures)==2
            and all(t['status']=='UNCHANGED_OUTPUT' for r in failures for t in r['trials']), 'numeric partition')
    old = load(PROGRESS / 'historical-failure-controls-rechecked.json'); historical=[]
    for row in old['cases']:
        proof=verify_case(row);require(proof==row['verification'],'historical failure changed')
        historical.append({k:v for k,v in row.items() if k!='verification'} | {'verification':proof})
    require(len(historical)==4 and old['historical_GPU_rerun']is False,'historical controls')
    # Adjacent tested512-byte settings, never a universal minimum assertion.
    thresholds=[]
    for depth,lower,upper in [(65,2048,2560),(96,2560,3072),(104,3072,3584),(120,3584,4096)]:
        good=next(r for r in positives if r['depth']==depth and r['reserve']==upper)
        if depth<=96:
            bad=next(r['verification'] for r in historical if r['depth']==depth and r['reserve']=='round')
            require(bad['new_word11']==lower and bad['native_code_SHA256']==good['native_code_SHA256'], 'threshold native code')
        else:
            bad=next(r for r in failures if r['depth']==depth and r['reserve']==lower)
            require(bad['native_code_SHA256']==good['native_code_SHA256'],'threshold native code')
        require(upper==((depth*32+511)&~511),'sampled source-depth relation')
        thresholds.append({'depth':depth,'lower_FAIL':lower,'upper_PASS':upper,'step':512,
                           'code_SHA256':good['native_code_SHA256'],'universal_minimum_proven':False})
    api = matrix(PROGRESS/'common-generalization-matrix.json',ROOT/'results/native-allocation-generalization-suite-20261016',LAB)
    public = matrix(PROGRESS/'public-generalization-matrix.json',ROOT/'results/native-allocation-public-generalization-suite-20261016',PUBLIC)
    require(len(api)==len(public)==2 and all(r['lifetime']for r in api+public),'API extension/lifetime coverage')
    pairs=[]
    for depth in [104,120]:
        roots=[under_results(next(r['result']for r in positives if r['depth']==depth)),
               ROOT/'results'/f'native-allocation-generalization-depth{depth}-20261016',
               ROOT/'results'/f'native-allocation-public-generalization-depth{depth}-20261016']
        files=sorted((roots[0]/'outputs').iterdir());require(len(files)==24,'semantic file set')
        for other in roots[1:]:
            for p in files:require(p.read_bytes()==(other/'outputs'/p.name).read_bytes(),'constructor/API/public semantic difference')
            pairs.append({'depth':depth,'left':roots[0].name,'right':other.name,'matching_files':24})
    for row in start['system_before']:require(sha(row['path'])==row['SHA256'],'system file changed')
    require(len(start['system_before'])==83 and sha('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist')==start['OCLP_SHA256'],'OCLP changed')
    positive_trials=sum(r['kernel_dispatches']for r in positives)+sum(r['trials']for r in api+public)
    wrong=sum(r['wrong_uint32_results']for r in failures)+sum(r['incorrect_uint32_values']for r in baseline)
    guards=sum(r['guard_bytes']for r in checked+baseline+api+public)
    return {'status':'PASS','scope':'Native allocation thresholds; two new source programs through unchanged common/public API',
            'base_commit':start['base_commit'],'new_native_observations':native_observations,
            'thresholds':thresholds,'sweep_cases':checked,'native_baselines':baseline,
            'common_API':api,'public_API':public,'semantic_file_pairs':pairs,
            'historical_failure_controls_rechecked':48,'historical_GPU_rerun':False,
            'new_positive_compute_trials':positive_trials,
            'new_numeric_failure_trials':sum(r['kernel_dispatches']for r in failures)+sum(r['trials']for r in baseline),
            'new_exact_uint32_results':sum(r['exact_uint32_results']for r in positives+api+public),
            'new_incorrect_uint32_results':wrong,'new_guard_bytes':guards,
            'common_archive_unchanged_SHA256':load(LAB/'manifest.json')['static_library_SHA256'],
            'public_archive_unchanged_SHA256':load(PUBLIC/'manifest.json')['static_library_SHA256'],
            'new_common_API_trials':sum(r['trials']for r in api),'new_public_API_trials':sum(r['trials']for r in public),
            'new_maximum_source_nesting_tested':120,'dynamic_hardware_CRS_depth_established':False,
            'general_allocation_rule_proven':False,'system_files_unchanged':83,'OCLP_unchanged':True,
            'Qwen_job_ids':[],'new_M1_executions':0,'performance_benchmark':False,'full_objective_complete':False,
            'next':'Map constructor allocation to actual submitted native CRS/QMD fields before automatic allocator integration',
            'limits':['Four sampled adjacent reservation thresholds, not a universal or minimum formula',
                      '25old+2new byte-bound listings; lexical join overlap is not actual dynamic stack depth',
                      'Common API remains pinned to reserve4096; intermediate settings are standalone experiments',
                      'New104/120 programs qualified; arbitrary shaders, graphics stages and transparent system integration remain open',
                      'Metadata quota changes are not measured VRAM savings or performance gains']}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    out=a.out.resolve();out.relative_to(ROOT/'results');proof=verify()
    with out.open('x')as f:json.dump(proof,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in proof.items()if k not in ['new_native_observations','thresholds','sweep_cases','native_baselines','common_API','public_API','semantic_file_pairs']},indent=2))
