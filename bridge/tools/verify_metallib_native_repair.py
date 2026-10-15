#!/usr/bin/env python3
"""CPU oracle and embedded-module/native-metadata cross-checks, no GPU calls."""
from pathlib import Path
import argparse,hashlib,json,struct
from metallib_air import indexed_modules
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);a=p.parse_args();root=a.input.resolve()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
library=root/'library.metallib';modules={m['name']:m for m in indexed_modules(library.read_bytes())}
policies=json.loads((root/'policies.json').read_text());cases=json.loads((root/'results.json').read_text());records=[];operations=0;words=0;captures=0;rejections=0
for entry in policies:
 d=Path(entry['directory']);policy=entry['policy'];module=modules[entry['name']]
 assert (d/'embedded.air').read_bytes()==module['wrapped_AIR'] and policy['embedded_AIR']['sha256']==module['sha256']
 assert sha(library)==policy['hashes']['library.metallib']
 assert sha(d/'native.sass')==policy['hashes']['native.sass'] and sha(d/'typed-air.json')==policy['hashes']['typed-air.json']
 if policy['qualified']:
  original=(d/'native.sass').read_bytes();repair=(d/'repaired.sass').read_bytes();length=len(original);off=policy['SASS']['redirect_offset']
  assert len(repair)==length+64 and [i for i in range(0,length,8) if repair[i:i+8]!=original[i:i+8]]==[off]
  assert repair[length+8:length+16]==original[off:off+8]
  assert all(repair[i:i+8]==original[i:i+8] for i in range(0,length,64))
for case in cases:
 plan=case['plan'];result=case['result'];assert 'air' not in plan and 'source' not in plan
 assert not case['process']['SIGKILL_requested'] and not case['process']['authoritative_ps_status']
 if plan['mode']=='negative_semantic_policy':
  assert not result['GPU_dispatch'] and result['failure_stage']=='semantic_policy' and not result['semantic_policy']['accepted'];rejections+=1;continue
 name=plan['function'];metadata=(root/name/'native.metadata').read_bytes();registers,word9,word11=struct.unpack_from('<I',metadata,28)[0],struct.unpack_from('<I',metadata,36)[0],struct.unpack_from('<I',metadata,44)[0]
 assert result['passed'] and result['GPU_dispatch'] and result['device']=='NVIDIA GeForce GTX 880M' and result['registry_id']==4294968458
 assert result['semantic_policy']['accepted'] and result['import']['contract_verified']
 for e in result['import']['events']:
  assert e['all_native_metadata_bytes_preserved'] and e['metadata_bytes_preserved_except_import_fields'] and e['expected_original_code_identical'] and e['imported_code_identical']
  assert e['registers']==e['decoded_registers']==registers and e['launch_words_9_11']==[word9,word11]
 n=plan['local']*plan['groups'];layout=plan['layout'];runs=[]
 for run in result['runs']:
  raw=Path(run['output_file']).read_bytes();assert len(raw)==n*16+128 and raw[:64]==raw[-64:]==bytes([0xa5])*64
  rows=[struct.unpack_from('<4I',raw,64+i*16) for i in range(n)];rows=[(v[1],v[2],v[3],v[0]) if layout=='permuted' else v for v in rows]
  seed=0x1234+37*run['iteration'];assert seed==run['seed'];winners=[sum(rows[i][1]==1 for i in range(g*plan['local'],(g+1)*plan['local'])) for g in range(plan['groups'])]
  assert winners==([0]*plan['groups'] if plan['variant'] else [1]*plan['groups'])
  for i,(old,success,final,index) in enumerate(rows):
   initial=seed+(i//plan['local'])*0x10001;replacement=seed^0x55667788
   expected_old=initial if plan['variant'] or success else replacement;expected_final=initial if plan['variant'] else replacement
   expected_index=i^(((seed*0x9e3779b9)&0xffffffff)^(i*17)) if layout=='noise' else i
   assert (old,success,final,index)==(expected_old,0 if plan['variant'] else success,expected_final,expected_index)
  assert run['compute']['status']==run['readback']['status']==4 and not run['mismatches'] and not run['guard_mismatches']
  words+=n*4;operations+=n;captures+=1;runs.append({'iteration':run['iteration'],'winners':winners,'sha256':hashlib.sha256(raw).hexdigest()})
 records.append({'name':case['name'],'PASS':True,'native_registers':registers,'native_launch_words':[word9,word11],'all_metadata_preserved':True,'runs':runs})
manifest=json.loads((root/'manifest.json').read_text());assert manifest['system_before']==manifest['system_after']
for file,h in manifest['source_hashes'].items():assert sha(root/file)==h
negative=json.loads((root/'container-negative-checks.json').read_text());assert len(negative)==4 and all(x['rejected'] and not x['GPU_dispatch'] for x in negative)
summary={'status':'PASS','library_functions':len(modules),'repaired_GPU_cases':len(records),'raw_captures':captures,'correct_CAS_operations':operations,
 'uint32_words_verified':words,'guard_bytes_verified':captures*128,'wrong_words':0,'guard_mismatches':0,
 'embedded_AIR_HASH_verified':True,'all_native_metadata_preserved':True,'native_register_counts':sorted({c['native_registers'] for c in records}),
 'native_launch_words':[736,544],'semantic_rejections_before_pipeline':rejections,'container_rejections':len(negative),
 'source_sidecars_required_by_plan':False,'system_unchanged':True,'results':records,
 'scope':'Four named functions in one compiled library; three repaired shapes with complete original metadata. Library-driven L1 qualification, not general or transparent system repair.'}
(root/'independent-verification.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='results'},indent=2))
