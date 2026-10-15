#!/usr/bin/env python3
"""Independent mixed-scope producer/index-consumer and pixel oracle."""
from pathlib import Path
import argparse,base64,hashlib,json,struct
from decode_native_commands import decode
COMPUTE='7478ba6e51f7bb4c466e60e4b07cf7af15c8abe04d04f3211cb2f1f2c6525911'
RENDER='965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7'
MANIFEST='225c1f1bf5aeb78ad89aa7444597e126926e033c57a16a80d32f269c2f9fa1be'
PRODUCER=[True,True,False,True,True,True,False,False,True]
CONSUMER=[True,True,True,False,True,True,False,True,True]
RECTS=[(3,4,13,9),(25,8,11,17),(9,30,21,11)]
def require(v,msg):
 if not v:raise ValueError(msg)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def u32(a,o):return struct.unpack_from('<I',a,o)[0]
def verify(root,current=False,portable=False):
 inp=json.loads((root/'inputs.json').read_text());d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());mode=d['mode']
 require(mode in ('prepare','execute') and d['passed'] and d['registry_id']==4294968458 and d['scope_restored'],'mode/device/restore differs')
 require(not d['system_modified'] and d['integration_level']==1 and not d['full_ICB_contract'] and not d['GPU_resident_ICB'],'scope differs')
 require(sha(root/'cpu_icb_gpu_indices.metallib')==inp['compute_library_SHA256']==d['compute_library_SHA256']==COMPUTE and sha(root/'render_state_carrier.metallib')==inp['render_library_SHA256']==d['render_library_SHA256']==RENDER and sha(root/'cpu_icb_gpu_indices.json')==inp['manifest_SHA256']==d['manifest_SHA256']==MANIFEST,'library/manifest differs')
 require(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'],'child not successfully terminal')
 if not portable:require(sha(root/'cpu_icb_mixed_probe')==m['original_binary_sha256'] and sha(root/'execution/cpu_icb_mixed_probe')==m['signed_binary_sha256'],'host binary differs')
 for name,h in inp['source_hashes'].items():
  require(sha(root/name)==h,'frozen source differs')
  if current:require(sha(Path(__file__).resolve().parents[1]/('src' if name.startswith('Kepler') or name.endswith(('.metal','.json')) else 'tools')/name)==h,'current source differs')
 domains=[x['command_domain'] for x in d['events'] if x['operation']=='newIndirectCommandBuffer'];require(domains.count('compute')==domains.count('render')==2,'simultaneous domain objects differ')
 register=[x for x in d['events'] if x['operation']=='register_render_domain'];require(len(register)==1 and register[0]['compute_domain_preserved'] and register[0]['device_class_unchanged'],'domain attachment changed device class/compute')
 require({x['case'] for x in d['rejections']}=={'cross_domain_CPU_copy','mixed_command_slots'} and all(x['rejected'] for x in d['rejections']),'domain refusals missing')
 require(len(d['runs'])==(9 if mode=='execute' else 1),'trial count differs')
 hashes={};out=root/'outputs';bindings=None;invocations=channels=colored_total=0
 def load(name):p=out/name;hashes[name]=sha(p);return p.read_bytes()
 for trial,r in enumerate(d['runs']):
  require(r['trial']==trial and r['producer_expected']==PRODUCER[trial] and r['consumer_expected']==CONSUMER[trial] and not r['mismatches'] and r['no_CPU_read_between_compute_and_render'],'trial flags differ')
  cv=r['compute_event']['evidence'];rv=r['render_event']['evidence'];compute=load(f'trial-{trial}.compute.bin');render=load(f'trial-{trial}.render.bin');prefix=load(f'trial-{trial}.prefix.bin')
  require(r['compute_event']['executed_indices']==([0] if PRODUCER[trial] else []) and r['render_event']['executed_indices']==([0] if CONSUMER[trial] else []),'reset/copy selection differs')
  if PRODUCER[trial]:
   require(len(compute)==464 and hashlib.sha256(compute).hexdigest()==cv['stream_SHA256'] and cv['native_preparation_GPU_dispatches']==0 and cv['raw_packet_copies']==1,'compute stream differs');ps=decode(compute)
   require([p['method'] for p in ps]==['0x180','0x1b0','0x1b4','0x180','0x1b0','0x1b4','0x2b4','0x2bc','0x110'],'compute methods differ');qmd=compute[184:440];rel=cv['elements'][0]['relocation'];require(qmd[187]==7 and qmd[0x50]==6 and rel['function']=='gpu_indices' and rel['library_SHA256']==COMPUTE and rel['native_register_count']==7,'native program metadata differs')
   require(rel['groups_shape']==[1,1,1] and rel['local_shape']==[32,1,1] and ps[2]['values'][:3]==[32,1,1] and ps[2]['values'][4:7]==[1,1,1],'compute geometry differs')
   require(len(rel['bindings'])==3 and all(b['native_table_address']==b['GPU_address']+b['offset'] for b in rel['bindings']),'native binding table differs');new={x['index']:x for x in rel['bindings']};require(new[0]['offset']==new[1]['offset']==64 and new[0]['length']==128 and new[1]['length']==132 and new[2]['offset']==256 and rel['constant_buffer_bytes']==1280,'resource bounds differ')
   if bindings:require(new==bindings,'reused producer resources changed')
   bindings=new
  else:require(not compute and not cv,'missing producer emitted commands')
  if CONSUMER[trial]:
   require(bindings is not None and len(render)==60 and len(prefix)==192 and hashlib.sha256(render).hexdigest()==rv['stream_SHA256'] and prefix==base64.b64decode(rv['native_state_prefix_base64']) and rv['native_primer_draw_removed'],'render framing differs');meta=rv['records'][0];require(meta['kind']==2 and meta['inherits_encoder_state'] and 'scissor' not in meta and meta['index_GPU_address']==bindings[0]['GPU_address'] and meta['index_offset']==64 and meta['index_buffer_length']==128,'producer-consumer GPU buffer differs')
   ps=decode(render);start=meta['index_GPU_address']+64;end=meta['index_GPU_address']+127;require(ps[0]['method']=='0x1644' and ps[0]['values']==[0] and ps[1]['method']=='0x17c8' and ps[1]['values']==[start>>32,start&0xffffffff,end>>32,end&0xffffffff,2] and ps[2]['method']=='0x3840' and ps[2]['values']==[4,3,1,0,0,0],'indexed draw data differs')
   x,y,w,h=RECTS[trial%3];s=decode(prefix);require(len(s)==16,'scissor framing differs')
   for i,p in enumerate(s):require(p['method_addresses']==[hex(0xe04+i*16),hex(0xe08+i*16)] and p['values']==[(x+w)<<16|x,(y+h)<<16|y],'inherited scissor differs')
  else:require(not render and not prefix and not rv,'missing consumer emitted commands')
  before=load(f'trial-{trial}.before.bin');after=load(f'trial-{trial}.after.bin');indices=load(f'trial-{trial}.indices.bin');counter=load(f'trial-{trial}.counter.bin');require(before==b'\xa5'*49664,'pre-commit image changed')
  expected_index=bytearray(b'\xa5'*128);expected_counter=bytearray(b'\xa5'*132);seed=0x1234+trial;mode_index=trial in (1,8);actual_producer=mode=='execute' and PRODUCER[trial]
  values=(1,1,1,seed) if actual_producer and mode_index else (0,1,2,seed) if actual_producer else (0,0,0,0x77777777);struct.pack_into('<4I',expected_index,64,*values);struct.pack_into('<I',expected_counter,64,32 if actual_producer else 0)
  require(indices==bytes(expected_index) and counter==bytes(expected_counter),'GPU index/stamp/counter/guards differ')
  if mode=='prepare':require(not r['committed'] and after==before,'prepare submitted/rendered');continue
  require(r['committed'] and r['command_status']==4 and r['counter']==(32 if PRODUCER[trial] else 0),'GPU completion/counter differs');expected=bytearray(b'\xa5'*256);rect=RECTS[trial%3];colored=0;draw=PRODUCER[trial] and CONSUMER[trial] and not mode_index
  for y in range(48):
   for x in range(64):
    c=draw and rect[0]<=x<rect[0]+rect[2] and rect[1]<=y<rect[1]+rect[3];colored+=c;expected.extend(struct.pack('<4f',.75,.125,.25,1) if c else bytes(16))
  expected.extend(b'\xa5'*256);require(after==bytes(expected) and colored==r['colored_pixels'],'CPU pixel/guard oracle differs');invocations+=32 if PRODUCER[trial] else 0;channels+=12288;colored_total+=colored
 if mode=='execute':require(invocations==192 and channels==110592 and colored_total==535,'totals differ')
 return {'status':'PASS','mode':mode,'mixed_compute_render_scope':True,'GPU_compute_invocations_counted':invocations,'correct_float32_channels':channels,'colored_pixels':colored_total,'GPU_producer_to_private_index_consumer_qualified':mode=='execute','single_main_command_buffer_no_intermediate_CPU_read':True,'missing_producer_consumer_reset_copies_qualified':mode=='execute','API_domain_refusals':2,'raw_files_verified':len(hashes),'raw_SHA256':hashes,'scope_restored':True,'all_children_terminal':True,'integration_level':1,'full_ICB_contract':False,'GPU_resident_ICB':False,'performance_benchmark':False,'system_modified':False,'portable_raw_verification_only':portable,'host_executable_SHA256_rechecked':not portable,'verifier_SHA256':sha(Path(__file__))}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--check-current-sources',action='store_true');p.add_argument('--portable',action='store_true');a=p.parse_args();root=a.input.resolve();r=verify(root,a.check_current_sources,a.portable);(root/'independent-verification.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='raw_SHA256'},indent=2))
