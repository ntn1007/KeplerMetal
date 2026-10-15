#!/usr/bin/env python3
"""Independent byte-level CPU oracle for the single-CAS GPU comparison.
Expected native failures are retained and cause a nonzero status, never hidden.
"""
from pathlib import Path
import argparse, hashlib, json, struct

parser=argparse.ArgumentParser();parser.add_argument('--input',type=Path,required=True)
parser.add_argument('--relocate-from',type=Path)
parser.add_argument('--relocate-to',type=Path)
args=parser.parse_args();root=args.input.resolve()
assert bool(args.relocate_from)==bool(args.relocate_to)
def resolve(path):
    path=Path(path)
    return args.relocate_to/path.relative_to(args.relocate_from) if args.relocate_from else path
cases=json.loads((root/'results.json').read_text());rows=[];all_words=0;all_guards=0;all_bad=0
for case in cases:
    plan=case['plan'];record=case['result'];mode=plan['mode'];variant=plan['variant'];runs=[]
    for run in record['runs']:
        path=resolve(run['output_file']);data=path.read_bytes();assert len(data)==144
        values=struct.unpack_from('<4I',data,64);seed=0x1234+37*run['iteration'];assert seed==run['seed']
        guards=sum(x!=0xa5 for x in data[:64]+data[-64:])
        if mode=='carrier_control':expected=(1^0x7a11beef,0,0xdeadbeef,0)
        else:
            swapped=values[1]
            # Permit weak-CAS spurious failure on an equal comparison. A known
            # unequal comparison cannot succeed and must update expected.
            expected=(seed,0 if variant else swapped,(seed^0x55667788) if swapped else seed,0)
        bad=[{'word':i,'observed':v,'expected':expected[i]} for i,v in enumerate(values) if v!=expected[i]]
        if mode!='carrier_control' and values[1]>1:bad.append({'error':'boolean outside 0/1'})
        assert run['compute']['status']==run['readback']['status']==4
        assert values==tuple(run['values'])
        runs.append({'iteration':run['iteration'],'path':str(path),'sha256':hashlib.sha256(data).hexdigest(),
                     'observed':values,'expected':expected,'bad_words':bad,'guard_mismatches':guards})
        all_words+=4;all_guards+=guards;all_bad+=len(bad)
    passed=all(not run['bad_words'] and not run['guard_mismatches'] for run in runs)
    assert passed==record['passed']
    if mode=='air_nak':
        assert record['import']['contract_verified'] and record['import']['target_imports']>=1
        assert all(e['imported_code_identical'] and e['metadata_bytes_preserved_except_import_fields'] for e in record['import']['events'])
        assert passed
    rows.append({'case':case['name'],'mode':mode,'space':plan['space'],'variant':variant,'passed':passed,'runs':runs})
summary={'cases':len(rows),'passed':sum(row['passed'] for row in rows),'failed':sum(not row['passed'] for row in rows),
         'captures':sum(len(row['runs']) for row in rows),'words':all_words,'bad_words':all_bad,'guard_mismatches':all_guards,
         'results':rows,'scope':'Byte-level validation of bounded own-process GPU outputs, not full CAS/Metal conformance or resident-code attestation.'}
(root/'independent-verification.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='results'},indent=2))
raise SystemExit(1 if all_bad or all_guards else 0)
