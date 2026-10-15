#!/usr/bin/env python3
"""Independent oracle for public-MSL→GPU IR→native Kepler execution."""
from pathlib import Path
import argparse,hashlib,json,struct
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify(root):
 root=Path(root);d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());inp=json.loads((root/'inputs.json').read_text());mode=d['mode'];rows=2 if mode=='copy'else 1;slots=3+rows;mask=0xffffffff
 profile=d.get('consumer_profile','combined');assert profile in ['combined','manifest'];version=d.get('command_IR_version',1);assert version in [1,2];dispatch=d.get('dispatch_kind','threadgroups');assert dispatch in ['threadgroups','threads'];kind=int(dispatch=='threads')
 mutations={'bad_flags':(1,0x177),'bad_tag':(3,0x4b504951),'bad_pipeline':(2,8),'bad_address':(12,1),'bad_parameters':(16,1),'bad_local':(8,0),'bad_shared':(18,49152),'bad_groups':(4,8),'bad_y':(5,2),'bad_threads':(7,1),'bad_stage':(1,0xf7),'bad_error':(19,1),'bad_reserved':(20,1)}
 assert mode in ['basic','barrier','clear','copy','reset','no_producer','split'] or mode in mutations
 assert d['public_MSL_command_IR_consumed'] and d['scope_restored'] and d['device']=='NVIDIA GeForce GTX 880M' and d['registry_id']==4294968458
 assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and m['GPU_reservation']['state']=='terminal'
 assert d['rows']==rows and d['slots']==slots and len(d['runs'])==3 and not d['choice_CPU_read_before_execution'] and not d['CPU_expected_answers_uploaded'] and not d['performance_benchmark']
 for n,h in inp['source_hashes'].items():assert sha(root/n)==h
 for n,h in inp['assets_SHA256'].items():assert sha(root/'assets'/n)==h
 assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256']
 assert d['producer_import']['contract_verified'] and not d['producer_import']['rejected_import']
 for e in d['producer_import']['events']:
  if e.get('code_replaced'):assert e['imported_code_identical'] and e['decoded_code_bytes']==d['producer_info']['code_bytes'] and e['decoded_registers']==d['producer_info']['registers']
 exact=invocations=guard_bytes=IR_records=0;files={};kinds=[]
 def load(name):p=root/'outputs'/name;files[name]=sha(p);return p.read_bytes()
 for t,r in enumerate(d['runs']):
  assert r['trial']==t and r['command_status']==4 and r['committed'] and r['intermediate_CPU_completion_waits']==0
  specs=r['node_specs'];locals_=[[32,33,128,256,512,1024],[512,1024,256,32,33,128],[128,256,32,1024,512,33]];names=['shared_mix_s128','shared_mix_s1024','shared_mix_s4096'] if profile=='combined' else ['manifest_mix','manifest_dynamic','manifest_dynamic'];statics=[512,4096,16384] if profile=='combined' else [0,0,0]
  for k,s in enumerate(specs):
   index=(k+t)%3;local=locals_[t][k];g=(4 if local==1024 else 7)if k<3 else 3;static=statics[index];dynamic=49152-static if k<3 else 1024*(k+1)
   if profile=='manifest':dynamic=0 if index==0 else (49152 if k<3 else 1024*(k+1))
   assert s=={'function':names[index],'local':local,'groups':g,'count':g*local,'seed':0x765431+t*97+k*101,'static_bytes':static,'dynamic_bytes':dynamic}
  bank=(t+1)%3;resource=(t+2)%3;spec=specs[bank];groups=1+0xa5a5a5a5%spec['groups'];requested=groups*spec['local']if kind else groups;live=mode not in ['reset','no_producer'] and mode not in mutations;empty_rows=[0]if mode=='copy'else list(range(rows))if mode=='reset'else [];flags=115 | (4 if spec['dynamic_bytes'] else 0) | (8 if mode=='barrier' else 0)
  records=load(r['input_file']);assert len(records)==1216
  assert records[:128]==b'\xa5'*128 and records[128+rows*128:]==b'\xa5'*(len(records)-128-rows*128)
  witness_stride=64 if version==2 else 32;witness=bytearray(b'\xa5'*(128+rows*witness_stride));witness[64:64+rows*witness_stride]=bytes(rows*witness_stride)
  counts=bytearray(b'\xa5'*(128+rows*8));counts[64:64+rows*8]=bytes(rows*8)
  for row in range(rows):
   raw=records[128+row*128:128+(row+1)*128];active=live and row not in empty_rows
   if mode=='no_producer':assert raw==b'\xa5'*128;status=2
   elif row in empty_rows:assert raw==struct.pack('<I',0x4b504952)+bytes(124);status=0
   else:
    words=list(struct.unpack('<32I',raw));changed=None
    if mode in mutations:
     word,value=mutations[mode]
     if mode=='bad_shared' and profile=='manifest':value=spec['dynamic_bytes']^16
     if mode=='bad_threads' and kind:word,value=4,1
     assert words[word]==value;changed=word
     expected={1:flags,2:bank,3:0x4b504950,4:requested,5:1,7:kind,8:spec['local'],18:spec['dynamic_bytes'],19:0,20:0}
     # Address mutations are not dereferenced; check the other address pairs.
     if word in expected:words[word]=expected[word]
    assert tuple(words[:4])==(0x4b504952,flags,bank,0x4b504950);assert tuple(words[4:8])==(requested,1,1,kind);assert tuple(words[8:12])==(spec['local'],1,1,0);assert words[18]==spec['dynamic_bytes'] and tuple(words[19:])==(0,)*13
    for i in [12,14,16]:
     if i!=changed:assert 0<(words[i]|words[i+1]<<32)<1<<40
    if changed!=12:assert words[12]%16==0
    assert words[14]%4==0
    if changed!=16:assert words[16]%256==0
    status=2 if mode in mutations else 1
   IR_records+=1
   # Invalid/reset native descriptor uses the retained template0 with zero X.
   matched_but_rejected=mode in ['bad_parameters','bad_local','bad_shared','bad_groups','bad_y','bad_threads','bad_reserved']
   selected_bank=bank if active else 0;selected_groups=groups if active else 0;selected_resource=resource if active or matched_but_rejected else 0
   if version==2:
    if mode in ['bad_flags','bad_stage']:selected_resource=resource
    struct.pack_into('<16I',witness,64+row*64,selected_groups,1,1,selected_bank,specs[selected_bank]['local'],1,1,selected_resource,status,0x4b504952,3,2,0,0,0,0x4b50524d)
   else:struct.pack_into('<8I',witness,64+row*32,selected_groups,specs[selected_bank]['local'],selected_bank,0x4b504952,selected_resource,3,status,0x4b50524d)
   struct.pack_into('<I',counts,64+rows*4+row*4,64)
  assert load(r['geometry_file'])==witness
  assert load(r['invocation_file'])==counts
  choice=load(r['choice_file']);assert choice[:64]==b'\xa5'*64 and choice[64:64+rows*16]==bytes(rows*16) and choice[64+rows*16:]==b'\xa5'*(len(choice)-64-rows*16)
  for k,(name,cn)in enumerate(zip(r['outputs'],r['counter_files'])):
   n=groups*spec['local'] if live and k==slots+resource else 0;expected=bytearray(b'\xa5'*(8192*16+512));counter=bytearray(b'\xa5'*208);oo=128 if k<slots else 128+32*(k-slots);co=128 if k<slots else 128+4*(k-slots);struct.pack_into('<I',counter,co,n)
   if n:
    seed=spec['seed'];local=spec['local'];sw=spec['static_bytes']//4;dw=spec['dynamic_bytes']//4
    for i in range(n):
     group,lane=divmod(i,local);fixed=lambda j:(seed*1664525 ^ group*1013904223 ^ j*2246822519 ^ 0x73193211)&mask;dynamic=lambda j:(seed*22695477 ^ group*747796405 ^ j*2891336453 ^ 0x11998877)&mask
     if profile=='combined':values=(sum(dynamic(j)for j in range(lane,dw,local))&mask,sum(fixed(j)for j in range(lane,sw,local))&mask,i,fixed((lane+1)%sw)^dynamic((lane*3+7)%dw))
     elif spec['function']=='manifest_mix':
      x=(seed*1664525 ^ i*1013904223)&mask;values=(((x<<13)|(x>>19))&mask,i,groups|(1<<16)|(1<<24),local)
     else:values=(sum((seed*1664525 ^ group*1013904223 ^ j*2246822519)&mask for j in range(lane,dw,local))&mask,i,groups|(1<<16)|(1<<24),local)
     struct.pack_into('<4I',expected,oo+i*16,*values)
    exact+=4*n;invocations+=n
   assert load(name)==expected,name;assert load(cn)==counter,cn;guard_bytes+=len(expected)-16*n+len(counter)-4
  IR_events=[e for e in r['events']if e['operation']=='GPU_command_IR_materialization'];assert len(IR_events)==1 and IR_events[0]['record_CPU_read'] is False and IR_events[0]['invalid_or_reset_zero_CTA']
  kinds.append({'trial':t,'candidate':bank,'resource':resource,'groups':groups if live else 0,'local':spec['local'],'function':spec['function']})
 receipt={'status':'PASS','mode':mode,'consumer_profile':profile,'command_IR_version':version,'dispatch_kind':dispatch,'runs':3,'IR_records_checked':IR_records,'exact_uint32_words':exact,'consumer_GPU_invocations_counted':invocations,'guard_bytes_verified':guard_bytes,'raw_files':len(files),'raw_SHA256':files,'selections':kinds,'IR_CPU_read_before_execution':False,'public_MSL_IR_consumed_on_GTX':True,'full_ICB_contract':False,'performance_benchmark':False}
 return receipt
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('directory',type=Path);a=p.parse_args();d=verify(a.directory);(a.directory/'independent-verification.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps({k:v for k,v in d.items()if k!='raw_SHA256'},indent=2))
