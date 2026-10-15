#!/usr/bin/env python3
"""Independent CPU oracle for the captured AIR-aware native-repair cohort.
Exit 0 means the whole experiment (including expected native/NOP failures)
matches its contract. Every known failed GPU result stays explicitly FAIL.
"""
from pathlib import Path
import argparse,hashlib,json,struct
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);a=p.parse_args();root=a.input.resolve()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
cases=json.loads((root/'results.json').read_text());policies=json.loads((root/'policies.json').read_text())
records=[];words=0;bad_words=0;guards=0;repair_ops=0;repair_captures=0;intent_ops=0;rejects=0
for f in policies:
 d=Path(f['directory']);policy=json.loads((d/'policy.json').read_text());assert policy==f['policy']
 for name,expected in policy['hashes'].items():assert sha(d/name)==expected
 if not policy['qualified']:
  assert f['fixture']=='original_compare_control' and not policy['AIR']['qualified'] and policy['SASS']['qualified'];continue
 original=(d/'native.sass').read_bytes();repaired=(d/'repaired.sass').read_bytes();nop=(d/'trampoline.sass').read_bytes();m=policy['SASS'];off=m['redirect_offset'];length=len(original)
 assert len(repaired)==len(nop)==length+64
 assert [i for i in range(0,length,8) if original[i:i+8]!=repaired[i:i+8]]==[off]
 assert all(original[i:i+8]==repaired[i:i+8] for i in range(0,length,64))
 assert repaired[length+8:length+16]==original[off:off+8]
 assert [i for i in range(0,len(repaired),8) if repaired[i:i+8]!=nop[i:i+8]]==[length+16]
 assert f'mov b32 $r{m["expected_register"]} $r{m["old_register"]}' in (d/'repaired.asm').read_text()
 for kind,expected in policy['replacement_hashes'].items():assert sha(d/(kind+'.sass'))==expected
for case in cases:
 plan=case['plan'];r=case['result'];mode=plan['mode'];local=plan['local'];groups=plan['groups'];n=local*groups
 assert not case['process']['authoritative_ps_status'] and not case['process']['SIGKILL_requested']
 if mode=='negative_semantic_policy':
  assert case['process']['exit_code']==12 and r['failure_stage']=='semantic_policy' and not r['GPU_dispatch']
  assert not r['semantic_policy']['accepted'] and not r.get('import');rejects+=1
  records.append({'name':case['name'],'status':'PASS','policy_rejected':True,'GPU_dispatch':False});continue
 assert r['device']=='NVIDIA GeForce GTX 880M' and r['registry_id']==4294968458 and r['GPU_dispatch']
 layout=plan['layout'];original_compare=plan['intent']=='original_comparand';runs=[]
 for run in r['runs']:
  raw=Path(run['output_file']).read_bytes();assert len(raw)==n*16+128
  rows=[struct.unpack_from('<4I',raw,64+i*16) for i in range(n)]
  standard=[(row[1],row[2],row[3],row[0]) if layout=='permuted' else row for row in rows]
  seed=0x1234+37*run['iteration'];assert seed==run['seed'];winners=[sum(standard[i][1]==1 for i in range(g*local,(g+1)*local)) for g in range(groups)];bad=[]
  for i,(old,success,final,index) in enumerate(standard):
   initial=(seed+(i//local)*0x10001)&0xffffffff;replacement=seed^0x55667788
   wanted_old=(initial^plan['variant']) if original_compare else initial if plan['variant'] or success else replacement
   wanted_index=i^(((seed*0x9e3779b9)&0xffffffff)^((i*17)&0xffffffff)) if layout=='noise' else i
   wanted=(wanted_old,0 if plan['variant'] else success,initial if plan['variant'] else replacement,wanted_index)
   if success not in (0,1):bad.append({'row':i,'field':'boolean','observed':success})
   for field,(value,expected) in enumerate(zip((old,success,final,index),wanted)):
    if value!=expected:bad.append({'row':i,'field':field,'observed':value,'expected':expected})
  assert winners==([0]*groups if plan['variant'] else [1]*groups),winners
  guard_bad=sum(b!=0xa5 for b in raw[:64]+raw[-64:]);assert guard_bad==run['guard_mismatches']==0
  assert run['mismatches']==len(bad) and run['compute']['status']==run['readback']['status']==4
  assert tuple(run['values'])==rows[0]
  words+=n*4;bad_words+=len(bad);guards+=128
  if mode=='native_repaired':repair_ops+=n;repair_captures+=1
  if original_compare:intent_ops+=n
  runs.append({'iteration':run['iteration'],'winners':winners,'bad_words':len(bad),'guard_mismatches':guard_bad,
               'output_sha256':hashlib.sha256(raw).hexdigest(),'first_bad':bad[:4]})
 passed=all(t['bad_words']==0 for t in runs)
 expected_pass=mode=='native_repaired' or original_compare
 assert passed==r['passed']==expected_pass
 assert case['process']['exit_code']==(0 if passed else 10)
 if mode!='native':
  assert r['semantic_policy']['accepted'] and r['import']['contract_verified']
  assert all(e['expected_original_code_identical'] and e['imported_code_identical'] and e['metadata_bytes_preserved_except_import_fields'] for e in r['import']['events'])
 records.append({'name':case['name'],'fixture':case['fixture'],'mode':mode,'status':'PASS' if passed else 'FAIL_EXPECTED_CONTROL',
                 'GPU_dispatch':True,'local':local,'groups':groups,'variant':plan['variant'],'runs':runs})
manifest=json.loads((root/'manifest.json').read_text());assert manifest['system_before']==manifest['system_after'] and manifest['audited_import_unchanged']
for file,expected in manifest['source_hashes'].items():assert sha(root/file)==expected
oldroot=root.parents[0]/'air-cas-final/threadgroup-native-compiler/native.sass'
assert (root/'original_compare_control/native.sass').read_bytes()==oldroot.read_bytes()
summary={'experiment_contract':'PASS','attempted_cases':len(records),'GPU_cases':sum(c['GPU_dispatch'] for c in records),
 'repaired_shaders':3,'repaired_GPU_cases':sum(c.get('mode')=='native_repaired' for c in records),
 'repaired_captures':repair_captures,'repaired_logical_CAS_operations':repair_ops,
 'original_comparand_control_operations':intent_ops,'policy_rejections_before_pipeline':rejects,
 'known_failed_GPU_controls':sum(c['status']=='FAIL_EXPECTED_CONTROL' for c in records),
 'raw_captures':sum(len(c.get('runs',[])) for c in records),'uint32_words_verified':words,
 'incorrect_words_in_preserved_controls':bad_words,'guard_bytes_verified':guards,'guard_mismatches':0,
 'dynamic_coordinates':{f['fixture']:f['policy']['SASS'] for f in policies if f['policy']['qualified']},
 'SASS_only_ambiguous_collision_verified':True,'system_unchanged':True,'all_children_terminal':True,
 'scope':'L1 bounded qualification on three new native shaders, AIR-aware diagnosis and exact fingerprints. General CAS, other Invalid Resource and automatic L3 integration remain unproven.',
 'results':records}
(root/'independent-verification.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ['results','dynamic_coordinates']},indent=2))
