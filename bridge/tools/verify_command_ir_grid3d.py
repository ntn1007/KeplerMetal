#!/usr/bin/env python3
"""Reconstruct all XYZ coordinates/geometry, records and guards from CPU data."""
from pathlib import Path
import argparse,hashlib,json,math,struct
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def verify(root):
 root=Path(root);d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());mode=d['mode'];native=d['native_reference'];rows=2 if mode=='copy'else 1;slots=6+rows
 assert m['exit_code']==0 and not m['SIGKILL_requested']and not m['authoritative_ps_status']and m['GPU_reservation']['state']=='terminal'
 assert d['rows']==rows and d['candidates']==6 and len(d['runs'])==6 and d['scope_restored']and not d['IR_CPU_read_before_execution']and not d['CPU_expected_answers_uploaded']and not d['performance_benchmark']
 if not native:
  inp=json.loads((root/'inputs.json').read_text());assert sha(root/'application')==inp['executable_SHA256']==m['original_binary_sha256']
  for n,h in inp['source_hashes'].items():assert sha(root/n)==h
  for n,h in inp['assets_SHA256'].items():assert sha(root/'assets'/n)==h
  assert d['device']=='NVIDIA GeForce GTX 880M'and d['registry_id']==4294968458 and d['producer_info']['command_ir_version']==2 and d['producer_import']['contract_verified']and not d['producer_import']['rejected_import']
  for e in d['producer_import']['events']:
   if e.get('code_replaced'):assert e['imported_code_identical']and e['decoded_code_bytes']==d['producer_info']['code_bytes']and e['decoded_registers']==d['producer_info']['registers']
 else:assert d['device']=='Apple M1 Max'
 shapes=[[7,4,1],[4,6,4],[3,4,2],[2,1,2],[2,3,1],[3,5,2]];locals_=[[8,4,1],[4,2,2],[5,3,2],[1,1,64],[32,32,1],[8,4,2]]
 exact=invocations=guards=0;files={};selections=[]
 def load(n):p=root/'outputs'/n;files[n]=sha(p);return p.read_bytes()
 def packed(v):return v[0]|v[1]<<10|v[2]<<20
 for trial,r in enumerate(d['runs']):
  assert r['trial']==trial and r['candidate']==trial and r['resource']==(trial+1)%3 and r['command_status']==4 and r['intermediate_CPU_waits']==0
  specs=r['node_specs'];assert len(specs)==slots+3
  for k,s in enumerate(specs):
   i=k if k<6 else trial;assert s=={'groups':shapes[i],'local':locals_[i],'seed':0x71931+trial*97+k*101,'max_count':math.prod(shapes[i])*math.prod(locals_[i])}
  local=locals_[trial];g=[1+0xa5a5a5a5%x for x in shapes[trial]];full=[a*b for a,b in zip(g,local)];n=math.prod(full);active=mode not in ['reset','no_producer']and not mode.startswith('bad_');resource=(trial+1)%3;selected=slots+resource
  for k,f in enumerate(r['files']):
   oo=128 if k<slots else 128+32*(k-slots);co=128 if k<slots else 128+4*(k-slots);live=n if active and k==selected else 0
   coords=bytearray(b'\xa5'*(8192*16+512));geom=bytearray(coords);counter=bytearray(b'\xa5'*256);struct.pack_into('<I',counter,co,live)
   for i in range(live):
    x=i%full[0];y=(i//full[0])%full[1];z=i//(full[0]*full[1]);p=[x,y,z];lane=[a%b for a,b in zip(p,local)];group=[a//b for a,b in zip(p,local)]
    struct.pack_into('<4I',coords,oo+i*16,x,y,z,i);struct.pack_into('<4I',geom,oo+i*16,packed(lane),packed(group),packed(g),packed(local)^specs[trial]['seed'])
   assert load(f['coordinates'])==coords,(mode,trial,k,'coordinates');assert load(f['geometry'])==geom,(mode,trial,k,'geometry');assert load(f['counter'])==counter,(mode,trial,k,'counter');exact+=8*live;invocations+=live;guards+=len(coords)+len(geom)+len(counter)-32*live-4
  record=load(r['record_file']);assert len(record)==1216
  if not native:
   assert record[:128]==b'\xa5'*128 and record[128+rows*128:]==b'\xa5'*(1216-128-rows*128)
   witness=bytearray(b'\xa5'*(128+rows*64));witness[64:64+rows*64]=bytes(rows*64)
   for row in range(rows):
    raw=record[128+row*128:256+row*128];empty=mode=='reset'or(mode=='copy'and row==0);live=active and not empty
    if mode=='no_producer':assert raw==b'\xa5'*128;status=2
    elif empty:assert raw==struct.pack('<I',0x4b504952)+bytes(124);status=0
    else:
     w=list(struct.unpack('<32I',raw));kind=1 if mode in ['threads','bad_threads']else 0;request=[a*b for a,b in zip(g,local)]if kind else g;flags=379 if mode=='barrier'else 371
     changed=None
     if mode.startswith('bad_'):
      mutations={'bad_flags':(1,0x1f3),'bad_pipeline':(2,8),'bad_address0':(12,1),'bad_address1':(14,1),'bad_address2':(16,1),'bad_parameters':(26,1),'bad_groups_x':(4,0),'bad_groups_y':(5,65536),'bad_groups_z':(6,65536),'bad_local_z':(10,0),'bad_kind':(7,9),'bad_stage':(20,1),'bad_reserved':(28,1),'bad_shared':(18,16),'bad_threads':(4+next(i for i,x in enumerate(local)if x>1),1)}
      changed,value=mutations[mode];assert w[changed]==value
      restore={1:flags,2:trial,4:request[0],5:request[1],6:request[2],7:kind,10:local[2],18:0,20:0,28:0}
      if changed in restore:w[changed]=restore[changed]
     assert w[:4]==[0x4b504952,flags,trial,0x4b504950]and w[4:8]==request+[kind]and w[8:12]==local+[0]and w[18:26]==[0]*8 and w[28:]==[0]*4
     for start in [12,14,16,26]:
      if start!=changed:assert 0<(w[start]|w[start+1]<<32)<1<<40
     status=2 if mode.startswith('bad_')else 1
    bank=trial if live else 0;chosenG=g if live else[0,1,1];chosenLocal=local if live else locals_[0];ri=resource if live or mode in ['bad_flags','bad_parameters','bad_groups_x','bad_groups_y','bad_groups_z','bad_local_z','bad_kind','bad_stage','bad_reserved','bad_shared','bad_threads']else 0
    # Resource matching runs even when a later field makes the command invalid.
    if mode=='bad_pipeline':ri=0
    if mode in ['bad_address0','bad_address1','bad_address2']:ri=0
    struct.pack_into('<16I',witness,64+row*64,*chosenG,bank,*chosenLocal,ri,status,0x4b504952,3,2,0,0,0,0x4b50524d)
   assert load(r['witness_file'])==witness,(mode,trial,'witness')
  selections.append({'trial':trial,'groups':g if active else[0,1,1],'local':local,'consumer_invocations':n if active else 0})
 return {'status':'PASS','mode':mode,'native_reference':native,'trials':6,'exact_uint32_words':exact,'consumer_invocations':invocations,'guard_bytes':guards,'raw_files':len(files),'raw_SHA256':files,'selections':selections,'performance_benchmark':False,'full_ICB_contract':False}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('directory',type=Path);p.add_argument('--receipt',type=Path);a=p.parse_args();d=verify(a.directory);target=a.receipt or a.directory/'independent-verification.json'
 with target.open('x')as f:json.dump(d,f,indent=2);f.write('\n')
 print(json.dumps({k:v for k,v in d.items()if k!='raw_SHA256'},indent=2))
