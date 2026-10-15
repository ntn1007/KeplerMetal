#!/usr/bin/env python3
"""Independently check raw native repair/control outputs and structural patch invariants."""
from pathlib import Path
import argparse, hashlib, json, struct
parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True)
args=parser.parse_args();root=args.input.resolve();cases=json.loads((root/'results.json').read_text());records=[]
words=0;failures=0;guards=0;repaired_ops=0
for case in cases:
    p=case['plan'];r=case['result'];mode=p['mode'];local=p['local'];groups=p['groups'];n=local*groups
    if mode=='negative_native_pin':
        assert r['failure_stage']=='pipeline' and not r.get('GPU_dispatch')
        assert not r['import']['contract_verified']
        assert all(not e.get('code_replaced') and not e.get('expected_original_code_identical') for e in r['import']['events'])
        records.append({'case':case['name'],'negative_input_rejected':True,'GPU_dispatch':False});continue
    runs=[]
    for run in r['runs']:
        data=Path(run['output_file']).read_bytes();assert len(data)==128+n*16
        rows=[struct.unpack_from('<4I',data,64+i*16) for i in range(n)];seed=0x1234+37*run['iteration'];assert seed==run['seed']
        winners=[sum(rows[i][1]==1 for i in range(g*local,(g+1)*local)) for g in range(groups)]
        bad=[]
        for i,row in enumerate(rows):
            initial=seed+(i//local)*0x10001;replacement=seed^0x55667788;old,swapped,final,index=row
            if p['variant']:
                expected=(initial,0,initial,i)
            else:
                # This preserved NVIDIA ld-lock/st-unlock loop gives one
                # winner in the observed cohort. Check the exact old-value set,
                # not only the final counter. This is stronger than generic weak CAS.
                expected=(initial if swapped else replacement,swapped,replacement,i)
                if swapped not in (0,1):bad.append({'row':i,'field':'boolean'})
            for field in range(4):
                if row[field]!=expected[field]:bad.append({'row':i,'field':field,'observed':row[field],'expected':expected[field]})
        if not p['variant']:
            for g,count in enumerate(winners):
                if count!=1:bad.append({'group':g,'field':'winner_count','observed':count})
        guard=sum(b!=0xa5 for b in data[:64]+data[-64:]);guards+=guard;failures+=len(bad);words+=n*4
        if mode=='native_repaired':repaired_ops+=n
        assert run['compute']['status']==run['readback']['status']==4
        assert rows[0]==tuple(run['values'])
        runs.append({'iteration':run['iteration'],'winners':winners,'bad_words_and_invariants':bad,
                     'guard_mismatches':guard,'output_sha256':hashlib.sha256(data).hexdigest()})
    passed=all(not t['bad_words_and_invariants'] and not t['guard_mismatches'] for t in runs)
    assert passed==r['passed']
    if mode!='native':
        assert r['import']['contract_verified'] and all(e['expected_original_code_identical'] for e in r['import']['events'])
        assert all(e['imported_code_identical'] and e['metadata_bytes_preserved_except_import_fields'] for e in r['import']['events'])
    assert not case['process']['authoritative_ps_status'] and not case['process']['SIGKILL_requested']
    if mode=='native_repaired':assert passed
    records.append({'case':case['name'],'mode':mode,'local':local,'groups':groups,'variant':p['variant'],'passed':passed,'runs':runs})
original=(root/'native-replay.sass').read_bytes();patched=(root/'native-repaired.sass').read_bytes();control=(root/'native-trampoline.sass').read_bytes()
assert len(original)==832 and len(patched)==len(control)==896
assert hashlib.sha256(original).hexdigest()=='ea09f179ff169422f6f3ac8c3b1f85f020c52f5853106e68becbb0f408ef85e3'
assert all(original[i:i+8]==patched[i:i+8] for i in range(0,len(original),8) if i!=0x2d0)
assert patched[0x348:0x350]==original[0x2d0:0x2d8]
assert all(patched[i:i+8]==control[i:i+8] for i in range(0,len(patched),8) if i!=0x350)
manifest=json.loads((root/'manifest.json').read_text());assert manifest['system_before']==manifest['system_after']
summary={'attempted_cases':len(records),'GPU_cases':sum('passed' in c for c in records),
         'passed_GPU_cases':sum(c.get('passed',False) for c in records),
         'known_control_failures':sum('passed' in c and not c['passed'] for c in records),
         'repaired_cases_passed':sum(c.get('mode')=='native_repaired' and c['passed'] for c in records),
         'raw_captures':sum(len(c.get('runs',[])) for c in records),'uint32_words':words,
         'bad_words_and_invariants_in_controls':failures,'guard_mismatches':guards,
         'repaired_logical_CAS_operations':repaired_ops,'negative_pin_rejected':any(c.get('negative_input_rejected') for c in records),
         'byte_preservation_verified':True,'system_files_unchanged':True,'results':records,
         'scope':'One exact native shader corrected in our own process; broader/native system support and general progression remain unproven.'}
(root/'independent-verification.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='results'},indent=2))
raise SystemExit(1 if failures or guards else 0)
