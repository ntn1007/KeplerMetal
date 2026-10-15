#!/usr/bin/env python3
"""Reconstruct input reduction, selected command, shared sums and all guards."""
from pathlib import Path
import argparse,hashlib,json,struct

sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def verify(root,portable=False):
 root=Path(root);read=lambda n:json.loads((root/n).read_text());d,m,inp=read('results.json'),read('execution/manifest.json'),read('inputs.json')
 mode=d['mode'];native=d['native_reference'];prepare=mode=='prepare';producer=mode!='no_producer';selector=mode!='no_selector';rows=2 if mode=='range'else 1;copy=mode=='copy';slots=3+rows*(2 if copy else 1)
 assert mode in ['prepare','select','range','split','completed','copy','no_producer','no_selector','refusals']
 assert d['candidate_count']==3 and d['rows']==rows and d['slots']==slots and d['scope_restored']
 assert d['device']==('Apple M1 Max'if native else'NVIDIA GeForce GTX 880M')and(native or d['registry_id']==4294968458)
 assert not any(d[k]for k in ['system_modified','choice_CPU_read_before_execution','CPU_expected_answers_uploaded','performance_benchmark','general_GPU_ICB_encoding'])
 assert m['exit_code']==0 and not m['SIGKILL_requested']and not m['authoritative_ps_status']and m['GPU_reservation']['state']=='terminal'
 for n,h in inp['source_hashes'].items():assert sha(root/n)==h
 for n,h in inp['assets_SHA256'].items():assert sha(root/'assets'/n)==h
 if not portable:assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256']and sha(root/'execution/application')==m['signed_binary_sha256']
 names=['shared_mix_s128','shared_mix_s1024','shared_mix_s4096'];statics=[512,4096,16384];locals_=[[32,33,128,256,512,1024],[512,1024,256,32,33,128],[128,256,32,1024,512,33]]
 mask=0xffffffff;hashes={};words=invocations=guards=0;selected=[];assert len(d['runs'])==3
 def load(n):p=root/'outputs'/n;hashes[n]=sha(p);return p.read_bytes()
 for t,r in enumerate(d['runs']):
  specs=[]
  for k in range(slots):
   index=(k+t)%3;l=locals_[t][k];g=3 if l<=33 else 5 if l==128 else 2 if l==256 else 1;sb=statics[index];db=49152-sb if k<3 else 1024*(k+1)
   specs.append({'function':names[index],'local':l,'groups':g,'count':g*l,'seed':0x765431+t*97+k*101,'static_bytes':sb,'dynamic_bytes':db})
  nonce=0x9e37+31*t;assert r['trial']==t and r['nonce']==nonce and r['node_specs']==specs
  assert r['committed']==(not prepare)and r['command_status']==(0 if prepare else 4)
  assert r['initial_outputs_untouched_after_preparation']and r['ICB_and_parameter_external_refs_released_before_commit']
  assert r['source_reset_after_completed_selector']==(mode=='completed')and r['intermediate_CPU_completion_waits']==(1 if mode=='completed'else 0)
  assert r['execute_index']==3+(rows if copy else 0)
  if mode=='refusals':
   expected={'wrong_selector_hash','changed_selector_bytes','zero_candidates','overlap','shared_input','short_input','unretained_buffer','other_queue','producer_reencoded','pending_producer_other_buffer','selector_reencoded','set_pipeline_after_GPU','set_buffer_after_GPU','set_geometry_after_GPU','set_shared_after_GPU','CPU_snapshot_GPU_selected'}
   assert not native and {x['case']for x in r['refusals']}==expected and all(x['refused']and x['events_unchanged']and x['reason']for x in r['refusals'])
  data=bytearray(b'\xa5'*(192+rows*128));choices=bytearray(b'\xa5'*(128+rows*16));counts=bytearray(b'\xa5'*(128+rows*8));choices[64:64+rows*16]=bytes(rows*16);counts[64:64+rows*8]=bytes(rows*8);multiplicity=[0]*slots;banks=[]
  for row in range(rows):
   values=[17*i+t*3+row*7+((2 if t==2 else t+1)if i==31 else 0)for i in range(32)]
   struct.pack_into('<32I',data,128+row*128,*values);total=sum(((x*1664525+1013904223)^nonce^(row*97))&255 for x in values);bank=total%3
   if producer and not prepare:struct.pack_into('<4I',choices,64+row*16,bank,total,0x4b504743,nonce);struct.pack_into('<I',counts,64+row*4,32)
   if selector and not prepare:struct.pack_into('<I',counts,64+rows*4+row*4,64)
   if not prepare:
    index=(bank if producer else 0)if selector else 3+row;multiplicity[index]+=1;banks.append(index);selected.append({'trial':t,'row':row,'candidate':index,'function':specs[index]['function'],'groups':specs[index]['groups'],'local':specs[index]['local']})
  assert load(r['input_file'])==data and load(r['choice_file'])==choices and load(r['invocation_file'])==counts
  for k,(name,cn)in enumerate(zip(r['outputs'],r['counter_files'])):
   spec=specs[k];active=multiplicity[k];n=spec['count'];seed=spec['seed'];local=spec['local'];sw=spec['static_bytes']//4;dw=spec['dynamic_bytes']//4;expected=bytearray(b'\xa5'*(8192*16+512));counter=bytearray(b'\xa5'*208);struct.pack_into('<I',counter,128,n*active)
   if active:
    for i in range(n):
     group,lane=divmod(i,local);fixed=lambda j:(seed*1664525 ^ group*1013904223 ^ j*2246822519 ^ 0x73193211)&mask;dynamic=lambda j:(seed*22695477 ^ group*747796405 ^ j*2891336453 ^ 0x11998877)&mask
     a=sum(dynamic(j)for j in range(lane,dw,local))&mask;b=sum(fixed(j)for j in range(lane,sw,local))&mask;w=fixed((lane+1)%sw)^dynamic((lane*3+7)%dw);struct.pack_into('<4I',expected,128+i*16,a,b,i,w)
    words+=n*4;invocations+=n*active
   assert load(name)==expected and load(cn)==counter;guards+=len(expected)-(n*16 if active else 0)+204
  if native:assert not r['events'];continue
  events=r['events'];producers=[e for e in events if e['operation']=='GPU_command_choice_producer'];selectors=[e for e in events if e['operation']=='GPU_command_descriptor_selection'];copies=[e for e in events if e['operation']=='GPU_QMD_copy'];execute=[e for e in events if e['operation']=='executeCommandsInBuffer']
  assert len(producers)==int(producer)and len(selectors)==int(selector)and len(copies)==int(copy)and len(execute)==1
  if producer:assert not producers[0]['input_CPU_read']and not producers[0]['choice_CPU_read']and not producers[0]['CPU_resolved_choice_supplied']
  if selector:
   e=selectors[0];assert e['candidate_count']==3 and len(e['rows'])==rows and e['producer_encoded']==producer and e['GPU_choice_clamped']and not e['descriptor_CPU_upload']and not e['choice_CPU_read']and not e['CPU_shadow_is_execution_source']
   assert e['owners_retained']==3+rows and not e['general_GPU_ICB_encoding']
  e=execute[0];assert e['executed_indices']==list(range(r['execute_index'],r['execute_index']+rows))
  if selector:
   assert e['resident_GPU_descriptor'];p=e['evidence'];assert p['command_bytes']==24*rows and p['CPU_QMD_uploads_in_launch']==p['CPU_constant_uploads_in_launch']==0
   assert p['owners']==slots
  else:assert not e.get('resident_GPU_descriptor',False)
  if copy:
   for pair in copies[0]['descriptor_pairs']:assert pair['GPU_selected_command']and pair['copied_function']is None and pair['copied_groups']is None
 return {'status':'PASS_REFUSALS_WITH_VALID_GPU_WITNESS','mode':mode,'native_reference':native,'exact_uint32_words':words,'GPU_invocations_counted':invocations,'selected_commands':selected,'raw_files':len(hashes),'raw_SHA256':hashes,'guard_bytes_verified':guards,'GPU_choice_and_command_copy_qualified':not prepare,'general_GPU_ICB_encoding':False,'integration_level':0 if native else 2,'performance_benchmark':False}


if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--out',type=Path);p.add_argument('--portable',action='store_true');a=p.parse_args();v=verify(a.root,a.portable)
 if a.out:a.out.write_text(json.dumps(v,indent=2)+'\n')
 print(json.dumps({k:x for k,x in v.items()if k not in ['raw_SHA256','selected_commands']},indent=2))
