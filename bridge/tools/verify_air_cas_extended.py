#!/usr/bin/env python3
"""Independent CPU oracle for multiple lanes/groups, including single-call contention."""
from pathlib import Path
import argparse, hashlib, json, struct
parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True)
args=parser.parse_args();root=args.input.resolve();cases=json.loads((root/'results.json').read_text())
checked=[];words=0;bad_total=0;guard_total=0;nak_ops=0
for case in cases:
    p=case['plan'];n=p['local']*p['groups'];runs=[]
    for run in case['result']['runs']:
        path=Path(run['output_file']);data=path.read_bytes();assert len(data)==128+n*16
        rows=[struct.unpack_from('<4I',data,64+i*16) for i in range(n)]
        seed=0x1234+37*run['iteration'];assert seed==run['seed']
        winners=[sum(rows[i][1]==1 for i in range(g*p['local'],(g+1)*p['local'])) for g in range(p['groups'])]
        failures=[]
        for i,(old,swapped,final,index) in enumerate(rows):
            g=i//p['local'];initial=seed+g*0x10001;replacement=seed^0x55667788
            expected_old={initial}
            if p['mode']=='carrier_control':expected=(n^0x7a11beef,0,0xdeadbeef,i)
            else:
                if swapped not in (0,1):failures.append({'row':i,'field':'boolean','observed':swapped})
                if p['variant'] and swapped:failures.append({'row':i,'field':'unexpected_swap'})
                if p['contended'] and not p['variant'] and not swapped:
                    expected_old={replacement} if p['mode']=='air_nak' else {initial,replacement}
                expected_final=(replacement if winners[g] else initial) if p['contended'] else (replacement if swapped else initial)
                expected=(next(iter(expected_old)),0 if p['variant'] else swapped,expected_final,i)
            for field,observed in enumerate((old,swapped,final,index)):
                valid=observed in expected_old if field==0 and p['mode']!='carrier_control' else observed==expected[field]
                if not valid:failures.append({'row':i,'field':field,'observed':observed,'expected':sorted(expected_old) if field==0 else expected[field]})
        if p['contended'] and not p['variant'] and p['mode']!='carrier_control':
            for g,count in enumerate(winners):
                if (count!=1 if p['mode']=='air_nak' else count>1):failures.append({'group':g,'field':'winner_count','observed':count})
        guards=sum(b!=0xa5 for b in data[:64]+data[-64:]);guard_total+=guards;bad_total+=len(failures);words+=n*4
        if p['mode']=='air_nak':nak_ops+=n
        assert run['compute']['status']==run['readback']['status']==4
        assert rows[0]==tuple(run['values'])
        runs.append({'iteration':run['iteration'],'elements':n,'winners':winners,'guard_mismatches':guards,
                     'failures':failures,'output_sha256':hashlib.sha256(data).hexdigest()})
    passed=all(not r['failures'] and not r['guard_mismatches'] for r in runs);assert passed==case['result']['passed']
    if p['mode']=='air_nak':
        assert passed and case['result']['import']['contract_verified']
        assert all(e['imported_code_identical'] and e['metadata_bytes_preserved_except_import_fields'] for e in case['result']['import']['events'])
    assert not case['process']['authoritative_ps_status'] and not case['process']['SIGKILL_requested']
    checked.append({'case':case['name'],'mode':p['mode'],'space':p['space'],'local':p['local'],
                    'groups':p['groups'],'contended':p['contended'],'variant':p['variant'],'passed':passed,'runs':runs})
summary={'cases':len(checked),'passed':sum(c['passed'] for c in checked),'failed':sum(not c['passed'] for c in checked),
         'captures':sum(len(c['runs']) for c in checked),'uint32_words':words,'bad_words_and_invariants':bad_total,
         'guard_mismatches':guard_total,'NAK_cases_passed':sum(c['mode']=='air_nak' and c['passed'] for c in checked),
         'NAK_logical_CAS_operations':nak_ops,'results':checked,
         'limits':'Native weak-CAS spurious failures allowed; NIR cmpxchg checked as nonspurious. Bounded single-call samples, not general progression/performance/full API conformance.'}
(root/'independent-verification.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='results'},indent=2))
raise SystemExit(1 if bad_total or guard_total else 0)
