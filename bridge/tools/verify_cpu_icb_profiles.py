#!/usr/bin/env python3
"""Independent integer/float/shared oracle and native-packet checks, no GPU calls.

Trial topology and expected programs come from this verifier, never from the
probe's expected_active/function/passed fields. Portable mode verifies archives
without pretending to attest omitted host executables or repeat GPU execution.
"""
import argparse, hashlib, json, struct
from pathlib import Path
from decode_native_commands import decode

LIBRARY='913c4c1a32db704bc0ee5e54c6d9084f8601418c924fbd35ef72bcc08cb64ecd'
SIZES=[(1,32),(3,33),(5,128),(3,33)]
ACTIVE=[{0,1,2},{1},{0,1,2},{0,1,2},{0,1,2},{0,2,3},{0,1,2},set()]
SLOTS=[[0,2,4],[2],[0,2,4],[0,2,4],[0,2,4],[0,2,4],[0,2,4],[]]
NODE_ORDER=[[0,1,2],[1],[0,1,2],[0,1,2],[0,1,2],[0,3,2],[0,1,2],[]]
MASK=(1<<32)-1
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def digest(d):return hashlib.sha256(d).hexdigest()
def require(c,s):
 if not c:raise ValueError(s)
def u32(d,o):return struct.unpack_from('<I',d,o)[0]
def function(trial,node):return 'profile_fma' if node==1 or node==0 and trial>=3 else 'profile_integer' if node==0 else 'profile_shared'

def verify(root,check_current=False,portable=False):
 inp=json.loads((root/'inputs.json').read_text());d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text())
 for name,h in inp['source_hashes'].items():
  require(sha(root/name)==h,'frozen source differs: '+name)
  if check_current:
   folder='src' if name.startswith('Kepler') or name.endswith('.metal') else 'tools'
   require(sha(Path(__file__).resolve().parents[1]/folder/name)==h,'current source differs: '+name)
 require(sha(root/'cpu_icb_profiles.metallib')==inp['library_SHA256']==d['library_SHA256']==LIBRARY,'library identity differs')
 require(sha(root/'foreign.metallib')==inp['foreign_library_SHA256']=='b15f9b198ba326811f0a61f64fc32ac7cc185d04db63fa8e04f86075e8450a8d','foreign control library differs')
 require(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'],'child not successfully terminal')
 if not portable:
  require(sha(root/'cpu_icb_profiles_probe')==m['original_binary_sha256'] and sha(root/'execution/cpu_icb_profiles_probe')==m['signed_binary_sha256'],'host executable identity differs')
 require(all(c['exit_code']==0 for c in json.loads((root/'commands.json').read_text())),'build/observation failed')
 require(d['registry_id']==4294968458 and d['registered_pipeline_count']==3 and d['scope_restored'] and not d['system_modified'] and d['integration_level']==1 and not d['ICB_contract_complete'],'scope/device differs')
 expected_controls={'wrong_library_SHA','foreign_pipeline_spoofed_label','shared_array_overflow','out_of_range','GPU_resource_identity','nonuniform_grid','descriptor_inheritance'}
 require({r['case'] for r in d['rejections']}==expected_controls and all(r['rejected'] for r in d['rejections']),'API rejection controls differ')
 mode=d['mode'];require(mode in ('execute','prepare'),'unknown mode');count=8 if mode=='execute' else 1
 require(len(d['runs'])==count,'trial count differs')
 events=d['events'];factories=[e for e in events if e['operation']=='newIndirectCommandBuffer'];material=[e for e in events if e['operation']=='materialize_CPU_command'];executions=[e for e in events if e['operation']=='executeCommandsInBuffer']
 require(len(factories)==2 and all(e['size']==5 and e['metadata_bytes']==2560 for e in factories),'factory backing differs')
 require(len(material)==(5 if mode=='execute' else 3) and all(e['requires_GPU_NOP_and_blit_preparation'] for e in material),'materialization/reuse differs')
 registration=[e for e in events if e['operation']=='registered_native_library'];require(len(registration)==1 and registration[0]['library_SHA256']==LIBRARY and set(registration[0]['functions'])=={'profile_integer','profile_fma','profile_shared'},'registered functions differ')
 require(events[0]['operation']=='scope_install' and not events[0]['capabilities_spoofed'] and events[-1]['operation']=='scope_restore' and events[-1]['device_class_restored'],'class scope lifecycle differs')
 require(len(d['cache_cycles'])==3,'cache qualification cycles differ')
 for cycle in d['cache_cycles']:
  require(cycle[0]['dynamic_class']==events[0]['dynamic_class'] and cycle[-1]['device_class_restored'] and cycle[-1]['cached_device_classes']==cycle[-1]['cached_encoder_classes']==1,'cached subclasses grew or failed restoration')
 raw={};out=root/'outputs'
 def load(name):
  p=out/name;data=p.read_bytes();raw[name]=sha(p);return data
 for prefix in ['before-execute']+(['materialization-0','materialization-3','materialization-5'] if mode=='execute' else ['materialization-0']):
  for node in range(4):
   require(load(f'{prefix}-{node}.output.bin')==b'\xa5'*10368,'pre-commit output changed')
   require(load(f'{prefix}-{node}.counter.bin')==b'\xa5'*64+bytes(4)+b'\xa5'*64,'pre-commit invocation occurred')
 require(len(executions)==count,'execute event count differs')
 programs={};packet_records=[];invocations=words=active_nodes=0
 for trial,(run,event) in enumerate(zip(d['runs'],executions)):
  require(run['trial']==trial and event['executed_indices']==SLOTS[trial],'trial/slot selection differs')
  require(event['location']==(2 if trial==1 else 0) and event['length']==(1 if trial==1 else 5),'range selection differs')
  stream=load(f'trial-{trial}.commands.bin');ev=event['evidence'];nodes=NODE_ORDER[trial]
  require(len(stream)==464*len(nodes),'actual command stream size differs')
  if nodes:
   require(digest(stream)==ev['stream_SHA256'] and ev['command_bytes']==len(stream) and ev['cursor_after']-ev['cursor_before']==len(stream),'actual packet capture/hash/cursor differs')
   require(ev['native_preparation_API_calls']==1 and ev['native_preparation_GPU_dispatches']==0 and ev['raw_packet_copies']==len(nodes) and len(ev['elements'])==len(nodes),'unexpected native dispatch/copy path')
  else:require(not ev,'empty ICB encoded a launch')
  for index,node in enumerate(nodes):
   part=stream[index*464:(index+1)*464];pack=decode(part);element=ev['elements'][index];rel=element['relocation'];name=function(trial,node);groups,local=SIZES[node]
   require([p['method'] for p in pack]==['0x180','0x1b0','0x1b4','0x180','0x1b0','0x1b4','0x2b4','0x2bc','0x110'] and all(p['subchannel']==1 for p in pack),'unexpected native packet methods')
   require([p['offset'] for p in pack]==[0,20,24,156,176,180,440,448,456] and [p['bytes'] for p in pack]==[20,4,132,20,4,260,8,8,8],'native packet framing differs')
   require(pack[0]['values'][:2]==[128,1] and pack[3]['values'][:2]==[256,1] and pack[1]['values']==pack[4]['values']==[17],'native upload lengths/options differ')
   require(not element['launch_suppressed'] and digest(part)==element['commands_SHA256']==rel['relocated_SHA256'] and rel['library_SHA256']==LIBRARY and rel['function']==name,'element/profile identity differs')
   cb=rel['dedicated_CB_GPU_address'];qmd_addr=rel['dedicated_QMD_GPU_address'];require(cb%256==qmd_addr%256==0,'unaligned allocations')
   require((pack[0]['values'][2]<<32)|pack[0]['values'][3]==cb+0x6f0,'constant upload relocation differs')
   require((pack[3]['values'][2]<<32)|pack[3]['values'][3]==qmd_addr,'QMD upload relocation differs')
   qmd=part[184:440];require(len(qmd)==256 and u32(qmd,0x48)&255==6,'QMD version differs')
   require(u32(qmd,0x30)==groups and u32(qmd,0x34)==65537 and u32(qmd,0x48)>>16==local and u32(qmd,0x4c)==65537,'QMD dimensions differ')
   require(u32(qmd,0x50)&255==6,'CB1/CB2 valid mask differs')
   require((u32(qmd,0x80)&255)<<32|u32(qmd,0x7c)==cb,'QMD CB1 relocation differs')
   require((u32(qmd,0x88)&255)<<32|u32(qmd,0x84)==rel['parameters_GPU_address'],'QMD parameter resource differs')
   shared=512 if name=='profile_shared' else 0;regs=8 if shared else 7
   require(u32(qmd,0x44)&0x3ffff==shared and u32(qmd,0xb8)>>24==regs,'static shared memory or native register metadata differs')
   require(pack[6]['values']==[qmd_addr>>8] and pack[7]['values']==[3] and pack[8]['values']==[0],'launch/serialize differs')
   offset=u32(qmd,0x20);require(offset!=0 and name not in programs or programs.get(name)==offset,'native program changed during reuse')
   programs[name]=offset;packet_records.append({'trial':trial,'node':node,'function':name,'program_offset':offset,'register_count':regs,'static_shared_bytes':shared,'SHA256':digest(part)})
  if mode=='prepare':require(not run['main_command_buffer_committed'] and not run['GPU_user_kernel_execution'],'prepare submitted a user kernel');continue
  require(run['command_status']==4 and run['GPU_user_kernel_execution'] and len(run['outputs'])==4,'GPU run incomplete')
  require(run['selected_buffer']==('copy' if trial in (4,6) else 'source'),'CPU copy selection differs')
  for node in range(4):
   output=load(f'trial-{trial}-node-{node}.output.bin');counter=load(f'trial-{trial}-node-{node}.counter.bin');groups,local=SIZES[node];n=groups*local;seed=0x1234+101*node+37*trial
   require(len(output)==10368 and len(counter)==132 and output[:64]==output[-64:]==counter[:64]==counter[-64:]==b'\xa5'*64,'resource guards differ')
   require(u32(counter,64)==(n if node in ACTIVE[trial] else 0),'GPU invocation count differs')
   if node not in ACTIVE[trial]:require(output==b'\xa5'*10368,'inactive node was written');continue
   expected=[];name=function(trial,node)
   for i in range(n):
    first=((seed*1664525)&MASK)^((i*1013904223)&MASK)
    if name=='profile_fma':first=struct.unpack('<I',struct.pack('<f',(i&31)*0.5+(seed&255)))[0]
    if name=='profile_shared':neighbor=(i//local)*local+(i%local+1)%local;first=((seed*1664525)&MASK)^((neighbor*1013904223)&MASK)
    expected.extend([first,i,groups|0x01010000,local])
   require(list(struct.unpack_from('<'+str(4*n)+'I',output,64))==expected,'CPU numerical oracle differs')
   require(output[64+n*16:-64]==b'\xa5'*((640-n)*16),'inactive output tail changed')
   invocations+=n;words+=4*n;active_nodes+=1
 require(len(programs)==len(set(programs.values()))==3,'three native programs were not distinguished')
 if mode=='execute':require(invocations==4725 and words==18900 and active_nodes==19,'experiment totals differ')
 return {'status':'PASS','mode':mode,'registered_native_programs':3,'user_GPU_invocations':invocations,'correct_uint32_words':words,'active_node_results':active_nodes,'submitted_user_command_buffers':8 if mode=='execute' else 0,'materialized_commands':len(material),'API_rejection_controls':7,'program_offset_identity_checked':True,'native_QMD_register_counts':[7,7,8],'native_static_threadgroup_bytes':[0,0,512],'precommit_raw_no_user_kernel_controls':16 if mode=='execute' else 8,'raw_files_verified':len(raw),'all_children_terminal':True,'scope_restored':True,'class_cache_reused_three_cycles':True,'system_modified':False,'ICB_contract_complete':False,'GPU_resident_ICB_indirection':False,'integration_level':1,'performance_benchmark':False,'portable_raw_verification_only':portable,'host_executable_SHA256_rechecked':not portable,'packet_records':packet_records,'raw_SHA256':raw,'verifier_SHA256':sha(Path(__file__))}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--check-current-sources',action='store_true');p.add_argument('--portable',action='store_true');a=p.parse_args();root=a.input.resolve();r=verify(root,a.check_current_sources,a.portable)
 (root/'independent-verification.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k not in ('packet_records','raw_SHA256')},indent=2))
