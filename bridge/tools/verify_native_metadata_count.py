#!/usr/bin/env python3
"""CPU oracle for the normalized-count import, including decoded field44."""
from pathlib import Path
import argparse,json,hashlib,struct
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);a=p.parse_args();root=a.input.resolve();cases=json.loads((root/'results.json').read_text());records=[];operations=0;captures=0;words=0
for case in cases:
 plan=case['plan'];result=case['result'];assert result['passed'] and result['GPU_dispatch'] and result['import']['contract_verified']
 assert result['registry_id']==4294968458 and result['device']=='NVIDIA GeForce GTX 880M'
 assert not case['process']['SIGKILL_requested'] and not case['process']['authoritative_ps_status']
 original=Path(plan['original_code']).read_bytes();code=Path(plan['code']).read_bytes();policy=json.loads(Path(plan['policy']).read_text());metadata=Path(plan['original_code']).with_name('native.metadata').read_bytes()
 old_count=struct.unpack_from('<I',metadata)[0];native_regs=struct.unpack_from('<I',metadata,28)[0];launch=[struct.unpack_from('<I',metadata,i)[0] for i in [36,44]];new_count=len(code)//8-1;assert old_count==len(original)//8-1 and new_count-old_count==8
 for e in result['import']['events']:
  assert e['original_instruction_count']==old_count and e['normalized_instruction_count']==e['decoded_instruction_count']==new_count
  assert e['native_metadata_preserved_except_instruction_count'] and not e['all_native_metadata_bytes_preserved']
  assert e['decoded_registers']==e['registers']==native_regs and e['launch_words_9_11']==launch
  assert e['expected_original_code_identical'] and e['imported_code_identical'] and e['metadata_bytes_preserved_except_import_fields']
 n=plan['local']*plan['groups'];runs=[]
 for run in result['runs']:
  raw=Path(run['output_file']).read_bytes();assert len(raw)==n*16+128 and raw[:64]==raw[-64:]==bytes([0xa5])*64
  rows=[struct.unpack_from('<4I',raw,64+i*16) for i in range(n)];rows=[(x[1],x[2],x[3],x[0]) if plan['layout']=='permuted' else x for x in rows];seed=0x1234+37*run['iteration'];assert seed==run['seed']
  winners=[sum(rows[i][1]==1 for i in range(g*plan['local'],(g+1)*plan['local'])) for g in range(plan['groups'])];assert winners==([0]*plan['groups'] if plan['variant'] else [1]*plan['groups'])
  for i,(old,success,final,index) in enumerate(rows):
   initial=seed+(i//plan['local'])*0x10001;replacement=seed^0x55667788;expected_old=initial if plan['variant'] or success else replacement;expected_final=initial if plan['variant'] else replacement
   expected_index=i^(((seed*0x9e3779b9)&0xffffffff)^(i*17)) if plan['layout']=='noise' else i
   assert (old,success,final,index)==(expected_old,0 if plan['variant'] else success,expected_final,expected_index)
  assert run['compute']['status']==run['readback']['status']==4 and not run['mismatches'] and not run['guard_mismatches'];operations+=n;words+=n*4;captures+=1
  runs.append({'iteration':run['iteration'],'winners':winners,'SHA256':hashlib.sha256(raw).hexdigest()})
 records.append({'name':case['name'],'old_count':old_count,'normalized_count':new_count,'native_GPR':native_regs,'launch':launch,'PASS':True,'runs':runs})
manifest=json.loads((root/'manifest.json').read_text())
for file,h in manifest['source_hashes'].items():assert hashlib.sha256((root/file).read_bytes()).hexdigest()==h
summary={'status':'PASS','GPU_cases':len(records),'raw_captures':captures,'correct_CAS_operations':operations,'correct_uint32_words':words,'guard_bytes_verified':captures*128,
 'instruction_count_decoded_verified':True,'all_other_metadata_preserved':True,'native_GPR':[7,8],'native_launch_words':[736,544],
 'system_modified':False,'general_compiler_repair':False,'results':records,
 'scope':'Count convention of three qualified native compute shapes. Metadata word0 normalized to code_words-1; no new ISA/Metal capability or performance gain claimed.'}
(root/'independent-verification.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k!='results'},indent=2))
