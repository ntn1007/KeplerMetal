#!/usr/bin/env python3
"""Independent buffer-data and native-command oracle; no GPU calls."""
import argparse,hashlib,json,struct
from pathlib import Path
from decode_native_commands import decode
LIBRARY='ba0f51c96f993240f9637f0b848e14a5362e125d9c5cdf2aa38efd518531a8fd'
MANIFEST='0c5f52ae67fdc53da8b9d43544b88173f67c4bdbe69e15797432315f6a55ca66'
COUNTS=[128,8192,65536]
def require(v,s):
 if not v:raise ValueError(s)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def u32(d,o):return struct.unpack_from('<I',d,o)[0]
def verify(root,current=False,portable=False):
 inp=json.loads((root/'inputs.json').read_text());d=json.loads((root/'results.json').read_text());m=json.loads((root/'execution/manifest.json').read_text())
 require(m['exit_code']==0 and not m['SIGKILL_requested'] and not m['authoritative_ps_status'],'child not successfully terminal')
 require(sha(root/'cpu_icb_buffers.metallib')==inp['library_SHA256']==d['library_SHA256']==LIBRARY and sha(root/'cpu_icb_buffers.json')==inp['manifest_SHA256']==d['manifest_SHA256']==MANIFEST,'library/manifest identity differs')
 for name,h in inp['source_hashes'].items():
  require(sha(root/name)==h,'frozen source differs: '+name)
  if current:
   folder='src' if name.startswith('Kepler') or name.endswith(('.metal','.json')) else 'tools';require(sha(Path(__file__).resolve().parents[1]/folder/name)==h,'current source differs: '+name)
 if not portable:require(sha(root/'cpu_icb_buffers_probe')==m['original_binary_sha256'] and sha(root/'execution/cpu_icb_buffers_probe')==m['signed_binary_sha256'],'host binary differs')
 control=next(r for r in d['rejections'] if r['case']=='insufficient_buffer_range');require(not control['main_command_buffer_committed'] and control['reason']=='Current schema2 buffer range is insufficient','range control is not causal')
 mode=d['mode'];require(mode in ('prepare','execute') and d['scope_restored'] and not d['system_modified'] and d['integration_level']==1 and not d['ICB_contract_complete'],'scope differs')
 require(d['source_file_deleted_before_load'] and d['mutable_caller_data_destroyed_before_execution'],'immutable-import controls missing')
 require({x['case'] for x in d['rejections']}=={'unknown_buffer_index','unaligned_buffer_offset','oversized_grid','insufficient_buffer_range'} and all(x['rejected'] for x in d['rejections']),'negative state controls missing')
 events=d['events'];registration=next(e for e in events if e['operation']=='registered_manifest_library');require(registration['library_loader']=='in_memory_dispatch_data' and registration['caller_data_copied'] and registration['manifest_schema']==2 and registration['max_kernel_bindings']==4 and not registration['registration_is_GPU_qualification'],'snapshot/registration contract differs')
 material=[e for e in events if e['operation']=='materialize_CPU_command'];executions=[e for e in events if e['operation']=='executeCommandsInBuffer'];count=4 if mode=='execute' else 1
 require(len(material)==(6 if mode=='execute' else 3) and len(d['runs'])==len(executions)==count,'materialization/reuse/trial count differs')
 raw={};program=None;processed=0
 def load(name):
  p=root/'outputs'/name;raw[name]=sha(p);return p.read_bytes()
 for prefix in ['before','materialized-0','range-rejected']+(['materialized-2'] if mode=='execute' else []):
  for node,n in enumerate(COUNTS):require(load(f'{prefix}-{node}.out.bin')==b'\xa5'*(n*16+1024),'unexpected pre-commit output')
 for trial,(run,event) in enumerate(zip(d['runs'],executions)):
  active=[1] if trial==1 else [0,1,2];offsets=[128,64,256,256] if trial<2 else [256,128,512,512];require(run['trial']==trial and event['executed_indices']==active,'range selection differs')
  stream=load(f'trial-{trial}.commands.bin');ev=event['evidence'];require(len(stream)==464*len(active)==ev['command_bytes'] and hashlib.sha256(stream).hexdigest()==ev['stream_SHA256'] and ev['cursor_after']-ev['cursor_before']==len(stream),'captured command stream differs')
  require(ev['native_preparation_API_calls']==1 and ev['native_preparation_GPU_dispatches']==0 and ev['raw_packet_copies']==len(active),'different replay path')
  for index,node in enumerate(active):
   part=stream[index*464:(index+1)*464];ps=decode(part);element=ev['elements'][index];r=element['relocation'];require([p['method'] for p in ps]==['0x180','0x1b0','0x1b4','0x180','0x1b0','0x1b4','0x2b4','0x2bc','0x110'] and all(p['subchannel']==1 for p in ps),'unexpected command methods')
   require(hashlib.sha256(part).hexdigest()==element['commands_SHA256']==r['relocated_SHA256'] and r['binding_layout_v2'] and r['function']=='bound_axpy' and r['library_SHA256']==LIBRARY,'native program/binding record differs')
   require(len(r['bindings'])==4 and [b['index'] for b in r['bindings']]==[0,1,2,3],'buffer table coverage differs')
   for i,binding in enumerate(r['bindings']):
    require(binding['offset']==offsets[i] and binding['native_table_address']==binding['GPU_address']+offsets[i] and binding['length']==(1536 if i==3 else COUNTS[node]*16+1024),'actual native buffer table differs')
   qmd=part[184:440];cb=r['dedicated_CB_GPU_address'];qd=r['dedicated_QMD_GPU_address'];require((ps[0]['values'][2]<<32)|ps[0]['values'][3]==cb+0x6f0 and (ps[3]['values'][2]<<32)|ps[3]['values'][3]==qd,'upload addresses differ')
   require(u32(qmd,0x30)==COUNTS[node]//128 and u32(qmd,0x34)==65537 and u32(qmd,0x48)>>16==128 and u32(qmd,0x4c)==65537 and qmd[187]==14 and u32(qmd,0x44)&0x3ffff==0 and qmd[0x50]==6,'native QMD metadata differs')
   require((u32(qmd,0x80)&255)<<32|u32(qmd,0x7c)==cb,'CB1 relocation differs')
   p=r['bindings'][3];require((u32(qmd,0x88)&255)<<32|u32(qmd,0x84)==p['GPU_address']+offsets[3] and u32(qmd,0x88)>>15==1536-offsets[3] and r['constant_buffer_bytes']==1536-offsets[3],'offset constant range differs')
   require(ps[6]['values']==[qd>>8] and ps[7]['values']==[3] and ps[8]['values']==[0],'launch/serialize differs')
   offset=u32(qmd,0x20);require(offset and (program is None or program==offset),'native code changed during reuse');program=offset
  if mode=='prepare':require(not run['main_command_buffer_committed'],'prepare submitted a user kernel');continue
  require(run['command_status']==4 and len(run['outputs'])==3,'command incomplete')
  for node,n in enumerate(COUNTS):
   seed=0x1234+37*trial+101*node;scale=-1.0 if trial%2 else 2.0;values_a=[];values_b=[]
   for i in range(n):
    for k in range(4):values_a.append(float((i*13+k*7+seed)%127)-63.0);values_b.append((float((i*19+k*11+seed)%61)-30.0)*0.5)
   payloads=[struct.pack('<'+str(4*n)+'f',*[x*scale+y for x,y in zip(values_a,values_b)]) if node in active else b'\xa5'*(16*n),struct.pack('<'+str(4*n)+'f',*values_a),struct.pack('<'+str(4*n)+'f',*values_b)]
   for kind,key in enumerate(['out','a','b']):
    wanted=b'\xa5'*offsets[kind]+payloads[kind]+b'\xa5'*(1024-offsets[kind]);require(load(f'trial-{trial}-node-{node}.{key}.bin')==wanted,'numerical payload/input preservation/guards differ')
   if node in active:processed+=n
 if mode=='execute':require(processed==229760,'processed vector total differs')
 return {'status':'PASS','mode':mode,'four_general_buffers':True,'immutable_library_import_controls':True,'source_constant_offsets_observed':([256,512] if mode=='execute' else [256]),'vector_counts_qualified':COUNTS if mode=='execute' else [],'processed_float4_elements':processed,'correct_float32_values':processed*4,'raw_files_verified':len(raw),'materialized_commands':len(material),'all_children_terminal':True,'scope_restored':True,'system_modified':False,'integration_level':1,'ICB_contract_complete':False,'GPU_resident_ICB':False,'performance_benchmark':False,'host_executable_SHA256_rechecked':not portable,'portable_raw_verification_only':portable,'raw_SHA256':raw,'verifier_SHA256':sha(Path(__file__)),'scope':'Native four-buffer AXPY with exact finite float data; byte-identical inputs and all guards verified. No arbitrary shader semantic/concurrent mutation/render or full ICB qualification.'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--check-current-sources',action='store_true');p.add_argument('--portable',action='store_true');a=p.parse_args();root=a.input.resolve();r=verify(root,a.check_current_sources,a.portable);(root/'independent-verification.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='raw_SHA256'},indent=2))
