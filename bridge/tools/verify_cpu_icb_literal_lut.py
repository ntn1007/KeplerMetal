#!/usr/bin/env python3
"""Independent integer/rotate/LUT oracle and recorded CB0 ownership checks."""
from pathlib import Path
import argparse,hashlib,json,struct
from decode_native_commands import decode
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(root,current=False,portable=False):
 inp=json.loads((root/'inputs.json').read_text()); d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());mode=d['mode']
 assert d['registry_id']==4294968458 and d['scope_restored'] and not d['system_modified']
 assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and m['GPU_reservation']['state']=='terminal'
 assert m['GPU_reservation']['lock_inherited_by_child'] and m['GPU_reservation']['bootstrap_process_table_checked']
 for n,h in inp['source_hashes'].items():
  assert sha(root/n)==h
  if current:assert sha(Path(__file__).resolve().parents[1]/('tools' if n.endswith('probe.mm') else 'src')/n)==h
 assert sha(root/'literal_lut.metallib')==inp['library_SHA256'] and sha(root/'used-manifest.json')==inp['used_manifest_SHA256']
 if not portable:assert sha(root/'cpu_icb_literal_lut_probe')==m['original_binary_sha256'] and sha(root/'execution/cpu_icb_literal_lut_probe')==m['signed_binary_sha256']
 if mode.startswith('reject-'):
  assert d['expected_rejection'] and d['main_command_buffers']==0
  assert d['failure_stage']==('registration' if mode=='reject-unqualified' else 'materialization')
  if mode=='reject-unqualified':assert 'literal-bank' in d['error']
  else:
   assert d['preparation_outputs_untouched'] and 'CB0' in d['error'] and d['count']==129 and d['seed']==0x6a17 and d['salt']==0x1713
   expected=b'\xa5'*64+b'\xcd'*(129*16)+b'\xa5'*(524416-64-129*16)
   assert len(d['outputs'])==4 and all((root/'outputs'/n).read_bytes()==expected for n in d['outputs'])
   counter=b'\xa5'*64+bytes(16)+b'\xa5'*64;assert (root/'outputs'/d['counter_file']).read_bytes()==counter
   source=bytearray(b'\xa5'*524416)
   for j in range(129):struct.pack_into('<4I',source,64+j*16,j^0x6a17,(j*0x9e3779b9+0x1713)&0xffffffff,(j*17)^0xa5192713,(j*29+0x8f1742a1)&0xffffffff)
   assert (root/'outputs'/d['input_file']).read_bytes()==bytes(source)
  return {'status':'PASS','mode':mode,'expected_refusal':True,'main_command_buffers':0,'negative_readback_raw_verified':mode=='reject-size'}
 prepare=mode=='prepare';native=mode=='native';assert len(d['runs'])==9 and d['native_literal_bank_sizes']==[256,256,512,1024] and not d['performance_benchmark']
 M=0xffffffff;table=[];state=0x17d904e3
 for i in range(256):state=(state*1664525+1013904223)&M;table.append(state^((i*0x9e3779b9)&M))
 assert json.loads((root/'cpu_icb_literal_lut_values.json').read_text())['values']==table
 invocations=words=guards=waits=records=0;hashes={}
 def load(n):p=root/'outputs'/n;raw=p.read_bytes();hashes[n]=hashlib.sha256(raw).hexdigest();return raw
 for t,r in enumerate(d['runs']):
  n=[129,8193,32768][t%3] if t<6 else 1025;seed=0x6a17+53*t;salt=0x1713+97*t;selected=[] if t==3 else [1,2] if t==4 else [0,1,2,3]
  assert r['trial']==t and r['count']==n and r['seed']==seed and r['salt']==salt and r['selected_indices']==selected and r['committed']==(not prepare) and r['command_status']==(0 if prepare else 4) and r['before_commit_untouched']
  assert r['locals']==([1024]*4 if t>=5 else [32,128,256,1024]) and r['parameter_offset']==(768 if t%2 else 512) and r['scope_restored_before_commit']==(t==8)
  if not native:
   event=r['execution_event'];assert event['executed_indices']==selected;ev=event['evidence'];stream=load(r['stream_file']);assert len(stream)==464*len(selected);records+=len(selected)
   if selected:
    assert hashlib.sha256(stream).hexdigest()==ev['stream_SHA256'];ps=decode(stream);assert len(ps)==9*len(selected)
    for k,i in enumerate(selected):
     rel=ev['elements'][k]['relocation'];cb0=rel['native_literal_bank_0'];qmd=stream[k*464+184:k*464+440]
     assert qmd[0x50]==7 and qmd[187]==14 and cb0['bytes']==[256,256,512,1024][i] and cb0['variant_owner_class']=='NVMTLFunctionVariant' and cb0['variant_owner_retained'] and not cb0['literal_contents_CPU_read']
     assert cb0['native_code_bytes']==576 and cb0['GPU_address']==cb0['native_code_GPU_address']+768
     assert rel['function']=='literal_lut_'+str([16,64,128,256][i]) and rel['native_register_count']==14 and rel['static_threadgroup_bytes']==0
     assert rel['local_shape']==[r['locals'][i],1,1] and rel['groups_shape']==[(n+r['locals'][i]-1)//r['locals'][i],1,1]
     assert [(b['index'],b['offset']) for b in rel['bindings']]==[(0,64),(1,64),(2,r['parameter_offset']),(3,64)]
     assert ps[9*k+8]['method']=='0x110' and ps[9*k+8]['values']==[0];waits+=1
   else:assert not ev
  inputExpected=bytearray(b'\xa5'*524416);values=[]
  for j in range(n):
   v=(j^seed,(j*0x9e3779b9+salt)&M,(j*17)^0xa5192713,(j*29+0x8f1742a1)&M);values.append(v);struct.pack_into('<4I',inputExpected,64+j*16,*v)
  assert load(r['input_file'])==bytes(inputExpected);guards+=len(inputExpected)-n*16
  for i,name in enumerate(r['outputs']):
   raw=load(name);expected=bytearray(b'\xa5'*524416);active=not prepare and i in selected;fnSeed=seed+37*i;fnSalt=salt+13*i;N=[16,64,128,256][i]
   for j,v in enumerate(values):
    if active:
     index=(j*5+fnSeed)&(N-1);a=table[index];b=table[(index^31)&(N-1)];shift=a&31;rot=((v[2]<<shift)|(v[2]>>(32-shift)))&M
     row=((v[0]+a)&M,((v[1]^b)+fnSalt)&M,rot^fnSeed,(v[3]*3+table[(index+7)&(N-1)])&M);struct.pack_into('<4I',expected,64+j*16,*row)
    else:expected[64+j*16:64+(j+1)*16]=b'\xcd'*16
   assert raw==bytes(expected);guards+=len(raw)-n*16
   if active:invocations+=n;words+=n*4
  expectedCounter=bytearray(b'\xa5'*144);struct.pack_into('<4I',expectedCounter,64,*[n if not prepare and i in selected else 0 for i in range(4)])
  assert load(r['counter_file'])==bytes(expectedCounter);guards+=128
 return {'status':'PASS','mode':mode,'main_command_buffers':0 if prepare else 9,'exact_uint32_words':words,'GPU_invocations_counted':invocations,'guard_bytes_verified':guards,'native_literal_bank_sizes':[256,512,1024],'literal_pool_owned_and_preserved':not native,'encoded_records':records,'native_WAIT_FOR_IDLE_packets':waits,'copy_reset_range_empty_lifetime_qualified':not prepare,'scope_restored':True,'all_children_terminal':True,'integration_level':1,'performance_benchmark':False,'raw_SHA256':hashes}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--current',action='store_true');p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args();v=verify(a.root.resolve(),a.current,a.portable)
 if a.out:a.out.write_text(json.dumps(v,indent=2)+'\n')
 print(json.dumps({k:x for k,x in v.items() if k!='raw_SHA256'},indent=2))
