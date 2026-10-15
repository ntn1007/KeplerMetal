#!/usr/bin/env python3
"""Raw GPU choice/indices, native FIFO and independent CPU raster oracle."""
from pathlib import Path
import argparse,base64,hashlib,json,math,struct
from verify_cpu_icb_combined import raster,packet
from verify_native_gpu_argument_choice import reduction
from decode_native_commands import decode
LIB='3f07a5bb05487244b82001dff6edeed23ace2bd10a32824be1cb727f29f17775'
SELECTOR='463dabbbb9538a9aef9baa6e421fe3d0d9783d3823acf12177225c3ad1c47494'
NAMES=['smooth','linear','flat','smooth','linear','linear','flat','linear','smooth']
COUNTS=[2,17,2,64,17,17,2,17,64];BASES=[3,5,3,3,5,5,3,5,3]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify(root,current=False,portable=False):
 inp=json.loads((root/'inputs.json').read_text());d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());execute=d['mode'].endswith('execute');icb=d['ICB']
 assert m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'] and d['passed'] and d['scope_restored'] and d['registry_id']==4294968458 and d['integration_level']==1
 assert not any(d[k] for k in ('system_modified','installed_driver_modified','GPU_resident_ICB','GPU_generated_ICB','general_GPU_handle_generation','performance_benchmark'))
 if not portable:assert sha(root/'cpu_icb_depth_gpu_probe')==m['original_binary_sha256'] and sha(root/'execution/cpu_icb_depth_gpu_probe')==m['signed_binary_sha256']
 assert sha(root/'combined_render_resources.metallib')==inp['library_SHA256']==d['library_SHA256']==LIB and sha(root/'gpu_argument_selector.metallib')==inp['selector_library_SHA256']==d['selector_library_SHA256']==SELECTOR and sha(root/'cpu_icb_depth_gpu_profiles.json')==inp['manifest_SHA256']==d['manifest_SHA256']
 for n,h in inp['source_hashes'].items():
  assert sha(root/n)==h
  if current and n!='verify_cpu_icb_depth_gpu.py':assert sha(Path(__file__).resolve().parents[1]/('src' if n.startswith('Kepler') or n.endswith(('.json','.metal')) else 'tools')/n)==h
 assert len(d['runs'])==9 and {r['case'] for r in d['rejections']}==({'selector_not_registered','choice_alignment','choice_range','pending_other_command_buffer'} if icb else {'selector_not_registered','choice_alignment','choice_range'}) and all(r['rejected'] for r in d['rejections']);channels=threads=writes=records=0;maximum=0;rawhash={};banks_seen=set()
 def load(n):p=root/'outputs'/n;rawhash[n]=sha(p);return p.read_bytes()
 for t,r in enumerate(d['runs']):
  produced=t not in (4,5);draw=t!=6;wide=t not in (0,2,4);ordinary=t in (0,3,8);bias=7 if t in (3,8) else 0
  assert r['trial']==t and r['committed']==execute and r['command_status']==(4 if execute else 0) and r['producer']==produced and r['consumer']==draw and r['wide_index']==wide and r['name']==NAMES[t] and r['instances']==COUNTS[t] and r['base_instance']==BASES[t] and r['base_vertex']==(-2 if bias else 5)
  assert r['producer_status']==(4 if execute else 0) and r['same_command_buffer']==(t!=7 or not execute) and r['source_mutated']==(t in (3,7)) and r['copied_and_source_reset']==(t in (3,7)) and r['ordinary_native_draw_after_ICB']==ordinary and not r['CPU_read_of_Private_choice'] and not r['CPU_read_of_Private_indices']
  names=['vertices','instances','indices16','indices32','dataset','choice','producer-counter'];inputs={n:load(f'trial-{t}.{n}.input.bin') for n in names};values=[17*i+t*3+((1 if t==4 else t&1) if i==31 else 0) for i in range(32)];assert struct.unpack_from('<32I',inputs['dataset'],64)==tuple(values)
  assert inputs['dataset'][:64]==b'\xa5'*64 and inputs['dataset'][192:]==b'\xa5'*64 and struct.unpack_from('<6I',inputs['indices32'],64)==(bias,)*6 and struct.unpack_from('<6H',inputs['indices16'],64)==tuple(range(bias,bias+6)) and struct.unpack_from('<4I',inputs['choice'],64)==(0,0,0,0) and struct.unpack_from('<I',inputs['producer-counter'],64)[0]==0
  config=load(f'trial-{t}.configuration.bin');assert struct.unpack_from('<4I',config,256)==(0x9e3779b9,bias,0,0) and config[:256]==b'\xa5'*256 and config[272:]==b'\xa5'*240
  total=reduction(values,0x9e3779b9);bank=total&1 if produced else 0
  if t==4:assert total&1==1 and bank==0
  banks=load(f'trial-{t}.banks.bin');assert banks[:256]==b'\xa5'*256 and banks[280:512]==b'\xa5'*232 and banks[536:]==b'\xa5'*488
  if t in (3,7):mutated=bytearray(banks);mutated[512]^=1;assert load(f'trial-{t}.banks-mutated.bin')==mutated
  e=r['execution_event'];rows=e.get('evidence',{}).get('sequence_records',[]);assert len(rows)==(1 if draw and icb else 0)
  if icb:assert e['executed_indices']==([0] if draw else [])
  for j,row in enumerate(rows):
   meta=row['record'];assert meta['name']==NAMES[t] and meta['library_SHA256']==LIB and meta['manifest_SHA256']==d['manifest_SHA256'] and meta['index_count']==6 and meta['instances']==COUNTS[t] and meta['base_vertex']==(-2 if bias else 5) and meta['base_instance']==BASES[t] and meta['kind']==(2 if wide else 1) and meta['index_offset']==64 and meta['index_buffer_length']==128 and meta['index_buffer_storage_mode']==2 and meta['fragment_buffers']==1 and not meta['CPU_read_of_index_contents_during_materialization']
   raw=load(f'trial-{t}.record-{j}.commands.bin');prefix=load(f'trial-{t}.record-{j}.prefix.bin');assert raw==packet(meta,6)==base64.b64decode(row['commands_base64']) and sha(root/'outputs'/f'trial-{t}.record-{j}.commands.bin')==meta['SHA256'] and base64.b64decode(row['primer_draw_base64'])==packet(meta,1) and row['native_primer_draw_removed'] and row['primer_vertex_count']==1
   assert prefix==base64.b64decode(row['prefix_base64']) and hashlib.sha256(prefix).hexdigest()==row['prefix_SHA256'];ps=decode(prefix) if prefix else []
   if ps and ps[0]['method']=='0xe04':
    assert len(ps)>=16
    for k,p in enumerate(ps[:16]):assert p['method']==hex(0xe04+k*16) and p['values']==[64<<16,48<<16]
    ps=ps[16:]
   assert not ps or len(ps)==1 and ps[0]['method']=='0x3ab0' and ps[0]['values']==[0];assert e['caller_pipeline_restored'] and e['caller_vertex_slots_restored']==2 and e['caller_fragment_slots_restored']==1;records+=1
  private=e.get('evidence',{}).get('Private_fragment_tables',[]);assert len(private)==(1 if draw and icb else 0)
  for p in private:assert p['GPU_selected'] and p['selected_bank'] is None and p['payload_SHA256'] is None and p['candidate_payload_SHA256']==[hashlib.sha256(banks[256+k*256:280+k*256]).hexdigest() for k in range(2)] and p['producer']=='native_GPU_choice_selector' and p['selector_library_SHA256']==SELECTOR and p['selection_storage_mode']==2 and p['selection_offset']==64 and p['same_command_buffer']==(t!=7 or not execute) and not p['CPU_access_to_Private_contents']
  tex=[];params=[]
  for k in range(2):
   v=load(f'trial-{t}.texture-{k}.bin');expected=bytearray()
   for y in range(48):
    for x in range(64):expected+=struct.pack('<4f',((x*3+y*5+k*7)&63)/64,((x*7+y*11+k*3)&63)/64,(((x^y)+k*5)&31)/32,1)
   assert v==expected;tex.append(v);p=load(f'trial-{t}.params-{k}.input.bin');assert p[:256]==b'\xa5'*256 and p[288:]==b'\xa5'*224 and struct.unpack_from('<8f',p,256)==((1,1,1,1,0,0,0,0) if k==0 else (.5,1.5,2,1,.125,.25,.5,0));params.append(p);assert load(f'trial-{t}.params-{k}.after.bin')==(p if execute else b'\xa5'*512)
  for n in names:
   expected=bytearray(inputs[n])
   if produced:
    if n=='choice':struct.pack_into('<4I',expected,64,bank,total,0x4b504742,0x9e3779b9)
    if n=='producer-counter':struct.pack_into('<I',expected,64,32)
    if n=='indices32':struct.pack_into('<6I',expected,64,*range(bias,bias+6))
   assert load(f'trial-{t}.{n}.after.bin')==(expected if execute else b'\xa5'*len(expected)),(t,n)
  table=load(f'trial-{t}.private-table.bin');counter=load(f'trial-{t}.selector-counter.bin');before=load(f'trial-{t}.image-before.bin');image=load(f'trial-{t}.image.bin');assert before==b'\xa5'*49664 and image[:256]==before[:256] and image[-256:]==before[-256:]
  if icb:
   wr=r['writer_event'];wrows=wr['evidence'].get('sequence_records',[]);assert wr['executed_indices']==[0] and len(wrows)==1
   row=wrows[0];commands=load(f'trial-{t}.writer.commands.bin');prefix=load(f'trial-{t}.writer.prefix.bin');assert commands==struct.pack('<6I',0xa0050e0c,4,3,1,0,0)==base64.b64decode(row['commands_base64']) and base64.b64decode(row['primer_draw_base64'])==struct.pack('<6I',0xa0050e0c,4,1,1,0,0) and prefix==base64.b64decode(row['prefix_base64']) and hashlib.sha256(prefix).hexdigest()==row['prefix_SHA256'];assert row['record']['name']=='stencil_writer' and row['record']['library_SHA256']=='965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7'
  else:assert r['writer_event']=={}
  if not execute:assert table==b'\xa5'*1024 and counter==b'\xa5'*512 and image==before and load(f'trial-{t}.depth.bin')==b'\xa5'*12800 and load(f'trial-{t}.stencil.bin')==b'\xa5'*12800;continue

  expected=bytearray(banks);expected[256:280]=banks[256+bank*256:280+bank*256];assert table==expected and counter[:256]==b'\xa5'*256 and counter[260:]==b'\xa5'*252 and struct.unpack_from('<I',counter,256)[0]==6;threads+=32 if produced else 0;writes+=6;banks_seen.add(bank)
  expected=[[0.,0.,0.,0.] for _ in range(64*48)]
  clear=.25 if t==2 else .5 if t in (3,8) else 1.
  compares=[1,1,4,2,7,1,1,0,3]
  assert r['clear_depth']==clear and r['depth_compare']==compares[t] and r['stencil_inverse']==bool(t%2)
  depth_expected=[clear]*(64*48)
  compare=[lambda a,b:False,lambda a,b:a<b,lambda a,b:a==b,lambda a,b:a<=b,lambda a,b:a>b,lambda a,b:a!=b,lambda a,b:a>=b,lambda a,b:True][compares[t]]
  if draw:
   indices=list(range(5,11)) if not wide or produced else [5]*6
   # Resolve visibility in submission order. Each accepted fragment writes its
   # depth, so strict compares let the first overlapping instance win.
   for instance in range(BASES[t],BASES[t]+COUNTS[t]):
    candidate=[[0.,0.,0.,0.] for _ in range(64*48)]
    raster(candidate,inputs['vertices'],inputs['instances'],64,128,1,instance,NAMES[t],(0,0,64,48),fetches=indices,texture=tex[bank],fragment_params=params[bank],sample_mode='linear' if NAMES[t]=='linear' and bank else 'read')
    for y in range(48):
     for x in range(64):
      j=y*64+x;mask=96*(x+.5)<64*(y+.5+48);allowed=not mask if t%2 else mask
      if candidate[j][3]!=0 and allowed and compare(.5,depth_expected[j]):expected[j]=candidate[j];depth_expected[j]=.5
  if ordinary:raster(expected,inputs['vertices'],inputs['instances'],1024,128,2,3,'linear',(0,0,16,48),texture=tex[0],fragment_params=params[0],sample_mode='read')
  z=load(f'trial-{t}.depth.bin');st=load(f'trial-{t}.stencil.bin');assert len(z)==len(st)==12800 and z[:256]==z[-256:]==st[:256]==st[-256:]==b'\xa5'*256
  assert list(struct.unpack_from('<3072f',z,256))==depth_expected,'depth output differs'
  for y in range(48):
   assert st[256+y*256+64:256+(y+1)*256]==b'\xa5'*192
   for x in range(64):assert st[256+y*256+x]==(7 if 96*(x+.5)<64*(y+.5+48) else 0)
  actual=struct.unpack_from('<12288f',image,256)
  for j,p in enumerate(expected):
   for k in range(4):a=actual[j*4+k];error=abs(a-p[k]);maximum=max(maximum,error);assert math.isfinite(a) and error<=2e-6,(t,j,k,a,p[k]);channels+=1
 assert d['runs'][-1]['classes_restored_before_commit']
 if execute:assert banks_seen=={0,1}
 return {'status':'PASS','mode':d['mode'],'main_command_buffers':10 if execute else 0,'render_command_buffers':9 if execute else 0,'correct_float32_channels':channels,'maximum_error':maximum,'tolerance':2e-6,'counted_producer_threads':threads,'counted_selector_word_writes':writes,'copied_indexed_records':records,'GPU_computed_choice_in_indexed_ICB_qualified':execute and icb,'GPU_generated_UInt32_indices_qualified':execute,'CPU_choice_value_supplied':False,'CPU_read_of_Private_choice':False,'producer_omission_static_indices_control':execute,'producer_omission_degenerate_indices_control':execute,'consumer_omission_control':execute,'completed_producer_reuse':execute,'negative_controls':4 if icb else 3,'combined_depth_stencil_GPU_choice_qualified':execute,'ICB':icb,'exact_depth_values':27648 if execute else 0,'exact_stencil_values':27648 if execute else 0,'copied_stencil_writer_records':9 if icb else 0,'scope_restored':True,'all_children_terminal':True,'integration_level':1,'GPU_resident_ICB':False,'GPU_generated_ICB':False,'performance_benchmark':False,'source_sha256':inp['source_hashes'],'independent_verifier_SHA256':sha(Path(__file__)),'verifier_revision_differs_from_frozen_copy':sha(root/'verify_cpu_icb_depth_gpu.py')!=sha(Path(__file__)),'raw_sha256':rawhash}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--current',action='store_true');p.add_argument('--portable',action='store_true');p.add_argument('--out',type=Path);a=p.parse_args();r=verify(a.root.resolve(),a.current,a.portable)
 if a.out:a.out.write_text(json.dumps(r,indent=2)+'\n')
 print(json.dumps({k:v for k,v in r.items() if k not in ('raw_sha256','source_sha256')},indent=2))
