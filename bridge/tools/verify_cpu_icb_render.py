#!/usr/bin/env python3
"""Independent public CPU-render-ICB packet, state and pixel oracle."""
from pathlib import Path
import argparse,base64,hashlib,json,struct
from decode_native_commands import decode
LIBRARY='965bed87530267bec5618a3b375ae116e60f1862fa65e7731aa33b42b870c4f7'
RECTS=[(3,4,13,9),(25,8,11,17),(9,30,21,11)]
ACTIVE=[[0,1,2],[1],[2],[0,1,2],[1],[2],[1,2],[0,1,2],[],[0,1,2],[0,1,2]]
KINDS=[[0,1,2],[1],[2],[0,1,2],[1],[2],[1,2],[0,1,2],[],[0,1,2],[1,2,2]]
PURPLE=[True,True,True,True,False,False,False,True,False,True,False]
def require(ok,msg):
 if not ok:raise ValueError(msg)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def index_bytes(kind,degenerate=False):
 n,o,fmt=(128,64,'<3H') if kind==1 else (192,96,'<3I');raw=bytearray(b'\xa5'*n);struct.pack_into(fmt,raw,o,*(((0,0,0) if kind==1 else (1,1,1)) if degenerate else (0,1,2)));return bytes(raw)
def draw(raw,meta,kind):
 ps=decode(raw);require(len(raw)==(24 if not kind else 60) and len(ps)==(1 if not kind else 3),'bare record framing differs')
 require(meta['kind']==kind and meta['inherits_encoder_state'] and 'scissor' not in meta and meta['bytes']==len(raw) and hashlib.sha256(raw).hexdigest()==meta['SHA256'],'record metadata differs')
 require(not meta['native_shader_code_patched'] and not meta['recording_command_buffer_committed'],'record scope differs')
 if kind:
  begin=meta['index_GPU_address']+meta['index_offset'];end=meta['index_GPU_address']+meta['index_buffer_length']-1
  require(meta['index_offset']==(64 if kind==1 else 96) and meta['index_buffer_length']==(128 if kind==1 else 192),'index allocation differs')
  require(ps[0]['method']=='0x1644' and ps[0]['values']==[0] and ps[1]['method']=='0x17c8' and ps[1]['values']==[begin>>32,begin&0xffffffff,end>>32,end&0xffffffff,kind],'index address/type differs')
 require(all(p['subchannel']==0 for p in ps) and ps[-1]['kind']=='one_increment' and ps[-1]['method']==('0x3840' if kind else '0x3830') and ps[-1]['values']==[4,3,2 if kind==2 else 1,0,0]+([0] if kind else []),'draw macro differs')
def verify(root,current=False,portable=False):
 inp=json.loads((root/'inputs.json').read_text());d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text());mode=d['mode']
 require(mode in ('prepare','execute') and d['passed'] and d['registry_id']==4294968458 and d['scope_restored'],'mode/device/restore differs')
 require(d['integration_level']==1 and not d['system_modified'] and not d['full_ICB_contract'] and not d['GPU_resident_ICB'],'scope differs')
 require(sha(root/'render_state_carrier.metallib')==inp['library_SHA256']==d['library_SHA256']==LIBRARY,'library differs')
 require(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'],'child not successfully terminal')
 if not portable:require(sha(root/'cpu_icb_render_probe')==m['original_binary_sha256'] and sha(root/'execution/cpu_icb_render_probe')==m['signed_binary_sha256'],'host binaries differ')
 for name,h in inp['source_hashes'].items():
  require(sha(root/name)==h,'frozen source differs')
  if current:require(sha(Path(__file__).resolve().parents[1]/('src' if name.startswith('Kepler') else 'tools')/name)==h,'current source differs: '+name)
 expected_neg={'mixed_compute_descriptor','inherit_buffers','foreign_pipeline','unaligned_index','zero_vertices','compute_command_domain','range_bounds'}
 require({x['case'] for x in d['rejections']}==expected_neg and all(x['rejected'] for x in d['rejections']),'rejection controls missing')
 require(len(d['runs'])==(11 if mode=='execute' else 1),'trial count differs')
 rawhash={};out=root/'outputs'
 def load(name):p=out/name;rawhash[name]=sha(p);return p.read_bytes()
 for kind in (1,2):require(load(f'initial.indices{16 if kind==1 else 32}.bin')==index_bytes(kind),'initial private index/guard differs')
 if mode=='execute':
  for kind in (1,2):require(load(f'degenerate.indices{16 if kind==1 else 32}.bin')==index_bytes(kind,True),'patched private index/guard differs')
 actual_events=[e for e in d['events'] if e['operation']=='execute_CPU_render_ICB'];require(len(actual_events)==len(d['runs']),'execute event count differs')
 material=[e for e in d['events'] if e['operation']=='materialize_CPU_render_command'];require(len(material)==(4 if mode=='execute' else 3) and all(e['GPU_render_dispatches']==0 for e in material),'materialization count differs')
 channels=purple_total=red_total=0
 for trial,run in enumerate(d['runs']):
  e=run['execution_event'];require(e==actual_events[trial] and run['trial']==trial and not run['mismatches'],'execution trace differs');require(e['executed_indices']==ACTIVE[trial],'range/reset/copy selection differs')
  stream=load(f'trial-{trial}.commands.bin');prefix=load(f'trial-{trial}.prefix.bin');ev=e['evidence'];rect=RECTS[trial%3];require(run['scissor']==list(rect),'caller scissor differs')
  if ACTIVE[trial]:
   require(ev['stream_bytes']==len(stream) and hashlib.sha256(stream).hexdigest()==ev['stream_SHA256'] and ev['native_primer_bytes']==216 and ev['native_state_prefix_preserved_bytes']==192 and ev['native_primer_draw_removed'],'stream/primer differs')
   require(ev['cursor_after']==ev['cursor_before']+192+len(stream) and ev['stream_base_address']==ev['cursor_before']+192 and e['caller_pipeline_restored'],'caller state/cursor differs')
   require(prefix==base64.b64decode(ev['native_state_prefix_base64']) and hashlib.sha256(prefix).hexdigest()==ev['native_state_prefix_SHA256'],'preserved prefix hash differs');ps=decode(prefix);require(len(ps)==16,'scissor prefix differs');x,y,w,h=rect
   for j,p in enumerate(ps):require(p['subchannel']==0 and p['method_addresses']==[hex(0xe04+j*16),hex(0xe08+j*16)] and p['values']==[(x+w)<<16|x,(y+h)<<16|y],'encoder scissor state differs')
   offset=0;require(len(ev['records'])==len(KINDS[trial]),'record count differs')
   for kind,meta in zip(KINDS[trial],ev['records']):n=24 if kind==0 else 60;draw(stream[offset:offset+n],meta,kind);offset+=n
   require(offset==len(stream),'record boundaries differ')
  else:require(not stream and not prefix and not ev,'empty ICB emitted work')
  before=load(f'trial-{trial}.before.bin');after=load(f'trial-{trial}.after.bin');require(before==b'\xa5'*49664,'before-commit sentinel changed')
  if mode=='prepare':require(not run['committed'] and after==before,'prepare committed/rendered');continue
  require(run['committed'] and run['command_status']==4,'render not completed')
  expected=bytearray(b'\xa5'*256);purple=red=0
  for y in range(48):
   for x in range(64):
    inrect=lambda r:r[0]<=x<r[0]+r[2] and r[1]<=y<r[1]+r[3]
    r=trial==0 and inrect(RECTS[1]);p=PURPLE[trial] and inrect(rect);red+=r;purple+=p and not r
    expected.extend(struct.pack('<4f',.25,.875,.5,1) if r else struct.pack('<4f',.75,.125,.25,1) if p else bytes(16))
  expected.extend(b'\xa5'*256);require(after==bytes(expected) and run['purple_pixels']==purple and run['red_pixels']==red,'CPU pixel/guard/caller-pipeline oracle differs');channels+=12288;purple_total+=purple;red_total+=red
 if mode=='execute':require(channels==135168 and purple_total==956 and red_total==187,'totals differ')
 return {'status':'PASS','mode':mode,'GPU_render_command_buffers':11 if mode=='execute' else 0,'correct_float32_channels':channels,'purple_pixels':purple_total,'caller_native_red_pixels':red_total,'public_render_ICB_selectors_exercised':True,'inherited_scissor_qualified':mode=='execute','caller_pipeline_after_ICB_qualified':mode=='execute','ranges_reset_CPU_copy_overlap_qualified':mode=='execute','private_indices_data_dependence_qualified':mode=='execute','materialized_commands':len(material),'API_rejection_controls':7,'scope_restored':True,'all_children_terminal':True,'raw_files_verified':len(rawhash),'raw_SHA256':rawhash,'integration_level':1,'full_ICB_contract':False,'GPU_resident_ICB':False,'performance_benchmark':False,'system_modified':False,'portable_raw_verification_only':portable,'host_executable_SHA256_rechecked':not portable,'verifier_SHA256':sha(Path(__file__))}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--check-current-sources',action='store_true');p.add_argument('--portable',action='store_true');a=p.parse_args();root=a.input.resolve();r=verify(root,a.check_current_sources,a.portable);(root/'independent-verification.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='raw_SHA256'},indent=2))
