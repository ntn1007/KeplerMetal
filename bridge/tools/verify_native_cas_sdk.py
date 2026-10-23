#!/usr/bin/env python3
"""Independent raw uint32 CAS oracle; never create a pipeline or dispatch."""
from pathlib import Path
import argparse,hashlib,json,struct
from verify_local_memory import verify_device_identity
from public_large_scratch import DRIVER_PROFILES
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(root,portable=False):
 d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());mode=d['mode']
 assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
 verify_device_identity(d)
 assert not d['system_modified'] and not d['performance_benchmark']
 if not portable:
  assert sha(Path(m['original_executable']))==m['original_binary_sha256']
  assert sha(Path(m['signed_executable']))==m['signed_binary_sha256']
 if mode=='negative':
  assert not d['runs'] and len(d['proofs'])==8
  for p in d['proofs']:
   assert not p['pipeline_created'];e=p['evidence']
   if p['case']<6:assert not e['gate_accepted'] and not e['constructor_entered']
   else:
    assert e['gate_accepted'] and e['constructor_restored'] and not e['native_import']['contract_verified']
    events=e['native_import']['events'];assert events
    if p['case']==6:assert any(not x.get('expected_original_code_identical',True) for x in events)
    else:assert any(not x.get('native_metadata_identical_to_certificate',True) for x in events)
  return {'status':'PASS','mode':mode,'pre_constructor_rejections':6,'constructor_pin_rejections':2,'user_GPU_command_buffers':0}
 prepare=mode=='prepare';native=mode=='native';assert d['caller_inputs_wiped_before_commit'] and len(d['proofs'])==5 and len(d['runs'])==90
 proofs={x['function']:x for x in d['proofs']}
 for function,p in proofs.items():
  assert p['pipeline_max_threads']>=1024
  if not native and function!='sdk_keep_comparand':
   e=p['evidence'];assert e['gate_accepted'] and e['immutable_library_data'] and e['constructor_restored'] and e['native_import']['contract_verified']
   assert e['native_import']['driver_sha256'] in DRIVER_PROFILES and e['native_import']['registry_id']==d['registry_id']
   assert e['native_import']['target_imports']==e['native_import']['verified_imports']>0
   for event in e['native_import']['events']:
    assert event['expected_original_code_identical'] and event['native_metadata_identical_to_certificate'] and event['imported_code_identical']
    assert event['native_metadata_preserved_except_instruction_count'] and event['decoded_instruction_count']==event['normalized_instruction_count']
    assert event['decoded_registers']==event['registers'] and event['code_input_unchanged_after_constructor']
 records=[];correctOps=0;correctWords=0;wrongNativeWords=0;guardBytes=0
 for r in d['runs']:
  n=r['local']*r['groups'];assert r['local'] in [33,128,1024] and r['groups']==3 and r['variant'] in [0,1] and r['iteration'] in [0,1,2]
  assert r['seed']==0x2468+53*r['iteration'];assert r['committed']==(not prepare) and r['command_status']==(0 if prepare else 4)
  rel=Path(r['file']);assert not rel.is_absolute() and '..' not in rel.parts
  raw=(root/'outputs'/rel).read_bytes();assert len(raw)==n*16+128 and raw[:64]==raw[-64:]==b'\xa5'*64;guardBytes+=128
  if prepare:assert raw==b'\xa5'*len(raw);continue
  rows=[struct.unpack_from('<4I',raw,64+i*16) for i in range(n)]
  if r['layout']=='permuted':rows=[(v[1],v[2],v[3],v[0]) for v in rows]
  winners=[sum(rows[i][1]==1 for i in range(g*r['local'],(g+1)*r['local'])) for g in range(3)]
  assert winners==([0]*3 if r['variant'] else [1]*3)
  bad=0
  for i,row in enumerate(rows):
   old,success,final,index=row;assert success in [0,1]
   initial=(r['seed']+(i//r['local'])*0x10001)&0xffffffff;replacement=r['seed']^0x55667788
   expectedOld=(initial^(1 if r['variant'] else 0)) if not r['candidate'] else (initial if r['variant'] or success else replacement)
   expectedFinal=initial if r['variant'] else replacement
   expectedIndex=(i^(((r['seed']*0x9e3779b9)&0xffffffff)^(i*17))) if r['layout']=='noise' else i
   expected=(expectedOld,success,expectedFinal,expectedIndex)
   differences=sum(a!=b for a,b in zip(row,expected));bad+=differences
   # Native defect controls must still perform the actual CAS and publish
   # correct success/final/index; only the returned expected component is bad.
   assert row[1:]==expected[1:]
  if native and r['candidate']:assert bad>0;wrongNativeWords+=bad
  else:assert bad==0;correctOps+=n;correctWords+=n*4
  records.append({'file':r['file'],'SHA256':hashlib.sha256(raw).hexdigest(),'wrong_words':bad,'winners':winners})
 return {'status':'PASS','mode':mode,'user_GPU_command_buffers':0 if prepare else 90,'correct_CAS_operations':correctOps,'correct_uint32_words':correctWords,'expected_native_defect_words':wrongNativeWords,'guard_bytes_verified':guardBytes,'repaired_candidates':4 if not native else 0,'caller_inputs_wiped_before_commit':True,'native_metadata_preserved_except_instruction_count':None if native else True,'constructor_restored':None if native else True,'integration_level':1 if prepare or native else 2,'general_compiler_repair':False,'performance_benchmark':False,'records':records}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args();r=verify(a.root.resolve(),a.portable)
 if a.out:a.out.write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps({k:v for k,v in r.items() if k!='records'},indent=2))
