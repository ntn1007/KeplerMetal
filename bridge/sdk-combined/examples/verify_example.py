#!/usr/bin/env python3
"""Raw CPU CAS oracle and native-CAS ownership/QMD checks; no GPU actions."""
from pathlib import Path
import argparse,hashlib,json,struct
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(root,current=False,portable=False):
 inp=json.loads((root/'inputs.json').read_text());d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());mode=d['mode'];prepare=mode=='prepare';native=mode=='native'
 assert d['registry_id']==4294968458 and d['scope_restored'] and d['caller_data_wiped_before_materialization'] and not d['system_modified'] and not d['performance_benchmark'];assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
 assert inp['core_source_compilations']==0
 for name,h in inp['source_hashes'].items():assert sha(root/name)==h
 if not portable:assert sha(root/'application')==inp['executable_SHA256']
 for name,h in inp['assets_SHA256'].items():assert sha(root/'assets'/name)==h
 if not portable:assert sha(root/'application')==m['original_binary_sha256'] and sha(root/'execution/application')==m['signed_binary_sha256']
 registration=d['registration'];assert registration['manifest_schema']==2 and registration['max_kernel_bindings']==2 and registration['caller_data_copied'] and len(registration['functions'])==5
 for p in registration['functions']:
  assert p['static_threadgroup_bytes']==256 and p['max_local']==1024
  assert [(a['index'],a['active']) for a in p['reflection']]==[(0,True),(1,True),(3,False)]
  proof=p['native_CAS_import']
  if not native and p['function']!='sdk_keep_comparand':
   assert proof['gate_accepted'] and proof['constructor_restored'] and proof['function']==p['function'] and proof['native_import']['contract_verified']
   for e in proof['native_import']['events']:assert e['expected_original_code_identical'] and e['native_metadata_identical_to_certificate'] and e['imported_code_identical'] and e['native_metadata_preserved_except_instruction_count'] and e['decoded_registers']==p['expected_register_count']
  else:assert not proof
 if mode=='register':assert not d['runs'];return {'status':'PASS','mode':mode,'registered_functions':5,'certified_pipelines':4,'user_kernel_dispatches':0}
 assert len(d['runs'])==6 and len(d['refusals'])==3;operations=words=wrongWords=records=guardBytes=0;hashes={};sizes=[64,256,1024,128,64]
 for t,r in enumerate(d['runs']):
  assert r['trial']==t and r['preparation_outputs_untouched'] and r['committed']==(not prepare) and r['command_status']==(0 if prepare else 4)
  expectedIndices=[] if t==4 else [1,2,3] if t==2 else [0,1,2,3,4];event=r['execution_event'];assert event['executed_indices']==expectedIndices;ev=event['evidence'];records+=len(expectedIndices)
  if expectedIndices:
   assert ev['raw_packet_copies']==len(expectedIndices) and ev['native_preparation_GPU_dispatches']==0
   for item,i in zip(ev['elements'],expectedIndices):
    rel=item['relocation'];assert rel['function']==r['outputs'][i]['function'] and rel['native_register_count']==(8 if i==2 else 7) and rel['static_threadgroup_bytes']==256 and rel['QMD_total_shared_bytes']==256
    assert rel['local_shape']==[1024 if t>=3 else sizes[i],1,1] and rel['groups_shape']==[2,1,1]
    assert [(b['index'],b['offset']) for b in rel['bindings']]==[(0,512),(1,64)] and all(b['native_table_address']==b['GPU_address']+b['offset'] for b in rel['bindings'])
  else:assert not ev
  for i,o in enumerate(r['outputs']):
   assert o['node']==i and o['active']==(i in expectedIndices);local=1024 if t>=3 else sizes[i];assert o['local']==local and o['groups']==2 and o['seed']==0x1357+29*t+101*i and o['variant']==(1 if t in [1,3] else 0)
   raw=(root/'outputs'/o['file']).read_bytes();hashes[o['file']]=hashlib.sha256(raw).hexdigest();assert len(raw)==32896
   active=not prepare and o['active'];n=local*2
   if not active:assert raw==b'\xa5'*len(raw);continue
   assert raw[:64]==b'\xa5'*64 and raw[64+n*16:]==b'\xa5'*(len(raw)-64-n*16);guardBytes+=len(raw)-n*16
   rows=[struct.unpack_from('<4I',raw,64+j*16) for j in range(n)]
   if o['layout']=='permuted':rows=[(v[1],v[2],v[3],v[0]) for v in rows]
   winners=[sum(rows[j][1]==1 for j in range(g*local,(g+1)*local)) for g in range(2)];assert winners==([0]*2 if o['variant'] else [1]*2);bad=0
   for j,row in enumerate(rows):
    old,success,final,index=row;assert success in [0,1];initial=o['seed']+(j//local)*0x10001;replacement=o['seed']^0x55667788
    expectedOld=(initial^(1 if o['variant'] else 0)) if not o['candidate'] else (initial if o['variant'] or success else replacement)
    expectedIndex=j^(((o['seed']*0x9e3779b9)&0xffffffff)^(j*17)) if o['layout']=='noise' else j
    wanted=(expectedOld,success,initial if o['variant'] else replacement,expectedIndex);assert row[1:]==wanted[1:];bad+=sum(a!=b for a,b in zip(row,wanted))
   if native and o['candidate']:assert bad>0;wrongWords+=bad
   else:assert bad==0;operations+=n;words+=n*4
  assert r['scope_restored_before_commit']==(t==5)
 return {'status':'PASS','mode':mode,'main_command_buffers':0 if prepare else 6,'encoded_records':records,'correct_CAS_operations':operations,'exact_uint32_words':words,'expected_native_wrong_words':wrongWords,'guard_bytes_verified':guardBytes,'native_CAS_pipelines_in_CPU_ICB':not native and not prepare,'inactive_argument_reflection_qualified':True,'bind_grid_refusals':3,'copy_reset_range_empty_precommit_closure_qualified':not prepare,'scope_restored':True,'all_children_terminal':True,'general_CAS_repair':False,'GPU_generated_ICB':False,'integration_level':1 if prepare or native else 2,'performance_benchmark':False,'raw_SHA256':hashes}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--current',action='store_true');p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args();r=verify(a.root.resolve(),a.current,a.portable)
 if a.out:a.out.write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps({k:v for k,v in r.items() if k!='raw_SHA256'},indent=2))
