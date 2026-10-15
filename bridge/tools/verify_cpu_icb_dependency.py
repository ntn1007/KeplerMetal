#!/usr/bin/env python3
"""Independent uint32 dependency/counter/guard and native WAIT_FOR_IDLE oracle."""
from pathlib import Path
import argparse,hashlib,json,struct
from decode_native_commands import decode
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(root,current=False,portable=False):
 inp=json.loads((root/'inputs.json').read_text());d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());mode=d['mode'];prepare=mode=='prepare';native=mode=='native';assert d['registry_id']==4294968458 and d['scope_restored'] and d['untracked_Private_resources'] and d['no_CPU_read_between_stages'] and not d['system_modified'] and not d['performance_benchmark'];assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status']
 for n,h in inp['source_hashes'].items():
  assert sha(root/n)==h
  if current:assert sha(Path(__file__).resolve().parents[1]/('tools' if n.endswith('probe.mm') else 'src')/n)==h
 assert sha(root/'dependency.metallib')==inp['library_SHA256']
 if not portable:assert sha(root/'cpu_icb_dependency_probe')==m['original_binary_sha256'] and sha(root/'execution/cpu_icb_dependency_probe')==m['signed_binary_sha256']
 assert len(d['runs'])==9;words=invocations=guardBytes=waits=negativeMismatch=0;rawhash={};mask=0xffffffff
 for t,r in enumerate(d['runs']):
  n=[128,8192,32768][t%3] if t<6 else 128 if t==8 else 8192;seed=0x7319+37*t;salt=0x1543+101*t;producer=t!=7
  assert r['trial']==t and r['count']==n and r['seed']==seed and r['salt']==salt and r['producer_present']==producer and r['committed']==(not prepare) and r['command_status']==(0 if prepare else 4) and r['before_commit_untouched']
  if not native:
   event=r['execution_event'];indices=[0,1,2] if producer else [1,2];assert event['executed_indices']==indices and event['barriers_requested_before_indices']==([1,2] if t<3 or t in [6,7] else []) and not event['concurrent_record_execution'];assert 'WAIT_FOR_IDLE' in event['barrier_policy']
   stream=(root/'outputs'/r['stream_file']).read_bytes();rawhash[r['stream_file']]=hashlib.sha256(stream).hexdigest();assert len(stream)==464*len(indices) and hashlib.sha256(stream).hexdigest()==event['evidence']['stream_SHA256']
   packets=decode(stream);assert len(packets)==9*len(indices)
   for i in range(len(indices)):p=packets[9*i+8];assert p['method']=='0x110' and p['values']==[0];waits+=1
   for element,index in zip(event['evidence']['elements'],indices):
    rel=element['relocation'];literal=rel['native_literal_bank_0'];assert rel['constant_buffer_valid_mask']==(7 if index==0 else 6)
    if index==0:assert literal['bytes']==256 and literal['variant_owner_retained'] and not literal['literal_contents_CPU_read'] and literal['GPU_address']==literal['native_code_GPU_address']+((literal['native_code_bytes']+255)&~255)
    else:assert not literal
  def seed_rows():return [((i+seed)&mask,((i*1664525+1013904223)&mask)^seed,((i^seed)+salt)&mask,(i*17)^salt) for i in range(n)]
  fullA=seed_rows();A=fullA if producer else [(0,0,0,0)]*n
  def gather(a):
   return [((a[(i*5+seed)&(n-1)][2]+salt)&mask,a[(i*5+seed)&(n-1)][0]^seed,(a[(i*5+seed)&(n-1)][3]+i)&mask,(a[(i*5+seed)&(n-1)][1]*3)&mask) for i in range(n)]
  B=gather(A)
  def finish(b):return [((b[n-1-i][1]+b[n-1-i][3])&mask,b[n-1-i][2]^salt,(b[n-1-i][0]+i)&mask,(b[n-1-i][3]+seed)&mask) for i in range(n)]
  C=finish(B);expected=[A,B,C]
  for stage,f in enumerate(r['outputs']):
   raw=(root/'outputs'/f).read_bytes();rawhash[f]=hashlib.sha256(raw).hexdigest();assert len(raw)==524416 and raw[:64]==b'\xa5'*64 and raw[64+n*16:]==b'\xa5'*(len(raw)-64-n*16);guardBytes+=len(raw)-n*16
   rows=list(struct.iter_unpack('<4I',raw[64:64+n*16]));assert rows==([(0,0,0,0)]*n if prepare else expected[stage])
   if not prepare:words+=n*4
  raw=(root/'outputs'/r['counter_file']).read_bytes();rawhash[r['counter_file']]=hashlib.sha256(raw).hexdigest();counts=struct.unpack_from('<3I',raw,64);wanted=(0,0,0) if prepare else (n if producer else 0,n,n);assert len(raw)==144 and raw[:64]==b'\xa5'*64 and raw[76:]==b'\xa5'*68 and counts==wanted;guardBytes+=132;invocations+=sum(counts)
  if not prepare and not producer:negativeMismatch=sum(a!=b for ra,rb in zip(C,finish(gather(fullA))) for a,b in zip(ra,rb));assert negativeMismatch>0
  assert r['scope_restored_before_commit']==(t==8)
 return {'status':'PASS','mode':mode,'main_command_buffers':0 if prepare else 9,'exact_uint32_words':words,'GPU_invocations_counted':invocations,'guard_bytes_verified':guardBytes,'native_WAIT_FOR_IDLE_packets_verified':waits,'missing_producer_final_wrong_words':negativeMismatch,'untracked_Private_dependency_chain_qualified':not prepare,'set_clear_copy_reset_barrier_state_qualified':not native,'all_dispatches_serialized':not native,'concurrent_dispatch_qualified':False,'scope_restored':True,'all_children_terminal':True,'integration_level':1,'performance_benchmark':False,'raw_SHA256':rawhash}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--current',action='store_true');p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args();r=verify(a.root.resolve(),a.current,a.portable)
 if a.out:a.out.write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps({k:v for k,v in r.items() if k!='raw_SHA256'},indent=2))
