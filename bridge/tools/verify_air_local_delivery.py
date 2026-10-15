#!/usr/bin/env python3
"""Recompute MSL/AIR local-memory proof, numeric oracles, pins and system hashes."""
from pathlib import Path
import argparse
import hashlib
import json
from verify_local_memory import verify as numeric

ROOT=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
load=lambda p:json.loads(Path(p).read_text())

def verify():
    build=ROOT/'results/air-local-programs-build-20261015-05'
    pm=load(build/'manifest.json');assert pm['status']=='PASS' and len(pm['programs'])==8
    assert sha(build/'compiler')==pm['compiler_SHA256']
    assert sha(ROOT/'tools/build_air_local_programs.py')==pm['builder_SHA256']
    for f,h in pm['source_SHA256'].items():assert sha(build/f)==h
    for f,h in pm['archives_SHA256'].items():assert sha(ROOT/'build/mesa'/f)==h
    for f in ['air_local_compile.c','KeplerLocalAIRLowering.inc','KeplerResourceABI.h']:
        original=ROOT/('tools' if f.endswith('.c') else 'src')/f
        assert sha(original)==sha(build/f)
    assert sha(build/'local_memory.air')==pm['AIR_SHA256']
    assert sha(ROOT/'src/kepler_local_memory.metal')==pm['MSL_SHA256']
    native=ROOT/'results/local-memory-native-probe-build-20261015'
    assert sha(native/'kepler_local_memory.metal')==pm['MSL_SHA256']
    for row in pm['programs']:
        name=row['name'];info=row['info']
        assert load(build/(name+'.json'))==info and info['source_language']=='MSL/AIR'
        assert sha(build/(name+'.sass'))==row['code_SHA256']
        listing=(build/('decode-'+name+'.stdout')).read_text()
        assert all(marker not in listing for marker in ['[unknown','???','INVALID'])
        if name in ['local32','local256','local1024']:
            nir=(build/name/'before-nak.nir.txt').read_text()
            assert 'load_scratch' in nir and 'store_scratch' in nir
        if name in ['pressure64','pressure96','pressure32_forced_spill']:
            assert info['spills_to_memory']>0 and info['fills_from_memory']>0
            assert 0<info['scratch_bytes']<=224
    cpu=ROOT/'results/air-local-CPU-contracts-20261015'
    cd=load(cpu/'verification.json');assert cd['status']=='PASS' and len(cd['cases'])==8
    assert cd['compiler_SHA256']==pm['compiler_SHA256'] and not cd['GPU_execution']
    assert sha(ROOT/'tools/verify_air_local_contracts.py')==cd['verifier_SHA256']
    for r in cd['cases']:
        if 'MSL_SHA256' in r:
            assert sha(cpu/r['name']/'test.metal')==r['MSL_SHA256']
            assert sha(cpu/r['name']/'test.air')==r['AIR_SHA256']
    for r in load(cpu/'commands.json'):assert r['exit_code']==r['expected_exit_code']
    runtime=ROOT/'results/local-memory-runtime-library-build-20261015-03'
    lm=load(runtime/'manifest.json');pin=sha(runtime/'libKeplerMetal.a')
    assert pin==lm['static_library_SHA256']=='59f3a04d6c9929ec5c22034234e27006675174e076855df26a5b584f88f245ac'
    for f,h in lm['source_SHA256'].items():
        assert sha(runtime/f)==h
        current=ROOT/f
        if not current.exists():
            assert f=='src/KeplerFP64Programs.inc'
            current=ROOT/'results/gpu-generated-bindings-sdk-build-20261014-02/KeplerMetalSDK/src/KeplerFP64Programs.inc'
        assert sha(current)==h
    qualifier=ROOT/'results/air-local-qualification-20261015'
    assert load(qualifier/'status.json')['status']=='PASS'
    cases=[];roots={}
    for row in load(qualifier/'history.json'):
        assert row['exit_code']==0
        if row['phase']!='CPU':continue
        root=Path(row['result']);inp=load(root/'inputs.json');d=load(root/'results.json')
        assert inp['static_library_SHA256']==pin
        assert inp['programs_manifest_SHA256']==sha(build/'manifest.json')
        assert sha(root/'local_memory_probe.mm')==sha(ROOT/'tools/local_memory_probe.mm')
        r=numeric(root);assert r['trials']==12
        if row['mode'].startswith('nak:'):
            name=d['program'];assert d['program_info']==load(build/(name+'.json'))
            assert root.joinpath('assets',name+'.sass').read_bytes()==build.joinpath(name+'.sass').read_bytes()
        else:
            assert d['native_reference'] and not d['program_replaced']
        roots[row['mode']]=root
        cases.append({'mode':row['mode'],**{k:v for k,v in r.items() if k!='files_SHA256'}})
    assert len(cases)==19
    assert sum(r['trials'] for r in cases if r['kernel_dispatches'])==180
    assert sum(r['trials'] for r in cases if not r['kernel_dispatches'])==48
    matched=0
    for name in ['local_control','local32','local256','local1024','pressure32','pressure64','pressure96']:
        original=roots[name];candidate=roots['nak:'+name]
        for f in (original/'outputs').iterdir():
            assert f.read_bytes()==(candidate/'outputs'/f.name).read_bytes();matched+=1
    start=load(ROOT/'results/air-local-memory-progress-20261015/start.json')
    for row in start['system_before']:assert sha(row['path'])==row['SHA256']
    assert len(start['system_before'])==83
    assert sha('/System/Library/CoreServices/OpenCore-Legacy-Patcher.plist')==start['OCLP_SHA256']
    return {'status':'PASS','compiler_SHA256':pm['compiler_SHA256'],'programs_manifest_SHA256':sha(build/'manifest.json'),
            'runtime_library_SHA256':pin,'runtime_changed':False,'MSL_SHA256':pm['MSL_SHA256'],
            'AIR_SHA256':pm['AIR_SHA256'],'cohorts':19,'positive_trials':180,'negative_trials':48,
            'exact_uint32_results':sum(r['exact_uint32_results'] for r in cases),
            'kernel_invocation_witnesses':sum(r['exact_uint32_results'] for r in cases)//4,
            'guard_bytes':sum(r['guard_bytes'] for r in cases),
            'negative_expected_words_absent':sum(r['negative_expected_words_absent'] for r in cases),
            'same_source_native_AIR_files_matched':matched,'CPU_contract_cases':8,'cases':cases,
            'programs':pm['programs'],'system_files_unchanged':83,'OCLP_unchanged':True,
            'Qwen_job_ids':[],'M1_reference':'NOT RUN','performance_benchmark':False,
            'full_objective_complete':False,'integration':'explicit process-local compiler/import contract',
            'limits':['3-buffer resource ABI; 16-byte static constant layout; full 1D groups and zero origin',
                      'Pinned native carrier; external CRS and larger frames not qualified',
                      'No general AIR/MSL/library compiler or installed-driver replacement']}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();result=verify();out=a.out.resolve();out.relative_to(ROOT/'results')
    with out.open('x') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:v for k,v in result.items() if k not in {'cases','programs'}},indent=2))
