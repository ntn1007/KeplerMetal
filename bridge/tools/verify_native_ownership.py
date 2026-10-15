#!/usr/bin/env python3
"""Cross-check live typed pointers, raw headers, backing GPU ranges and lifetimes."""
from pathlib import Path
import argparse,hashlib,json,struct
from objc_type_layout import layout
from decode_native_commands import decode
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--retention',type=Path,required=True);a=p.parse_args();root=a.input.resolve();retention=a.retention.resolve()
observed=json.loads((root/'ownership.json').read_text());assert not observed['GPU_dispatch'] and not observed['committed'] and not observed['private_memory_writes']
def read_snapshot(record):
 data=Path(record['path']).read_bytes();assert record['saved'] and len(data)==record['bytes_read']==record['bytes_requested'] and hashlib.sha256(data).hexdigest()==record['SHA256'];return data
def u64(data,o):return struct.unpack_from('<Q',data,o)[0]
def ivar(obj,name):return next(r for r in obj['ivars'] if r['name']==name)
objects=observed['objects'];queue=objects['queue'];device_cpp=ivar(objects['device'],'_device')['raw_first_word'];queue_cpp=ivar(queue,'_queue')['raw_first_word']
qt=layout(ivar(queue,'_queue')['type'][1:]);assert qt['size']==144 and qt['fields'][1]['offset']==8 and qt['fields'][1]['name']=='InternalTextures'
ct=layout(ivar(observed['records'][0]['encoded'],'_cmdbuf')['type'][1:]);assert ct['size']==2664
offsets={f['type']:f['offset'] for f in ct['fields'] if f['type'].startswith('^')};assert offsets['^{Device}']==0x118 and offsets['^{CommandQueue}']==0x120 and offsets['^{State}']==0x128 and offsets['^{PushBuffer}']==0x130
backing={r['cpp_offset']:r for r in observed['queue_internal_objects']['fields'] if 'GPU_address' in r};assert len(backing)==5 and backing[16]['length']==4096 and backing[32]['length']==393216
for b in [objects[x] for x in ['args','counter','output','parameters']]+[x['layout']|{'GPU_address':x['GPU_address']} for x in backing.values()]:
 raw=read_snapshot(b['object_snapshot']);res=ivar(b,'_res');assert res['offset']==24 and res['type'].startswith('{_MTLIOAccelResource=')
 assert u64(raw,32)==b['GPU_address'],'Vendor reserved[1] vs public gpuAddress differs'
for r in backing.values():assert r['layout']['class']=='NVMTLBuffer'
records=[];streams=[];per_cb_state=[]
for row in observed['records']:
 enc=row['encoder'];cb=row['encoded'];impl=read_snapshot(ivar(enc,'m_compute')['prefix']);native_cb=read_snapshot(ivar(cb,'_cmdbuf')['prefix']);push=read_snapshot(row['push']);state=read_snapshot(row['state']);large=read_snapshot(row['device_cpp'])
 assert u64(impl,8)==u64(state,0)==device_cpp and u64(impl,16)==queue_cpp and u64(impl,24)==ivar(cb,'_cmdbuf')['raw_first_word']
 assert u64(impl,32)==row['cursor_after']['push'] and u64(impl,40)==row['cursor_after']['state']
 for ty,wanted in [('^{Device}',device_cpp),('^{CommandQueue}',queue_cpp),('^{State}',row['cursor_after']['state']),('^{PushBuffer}',row['cursor_after']['push'])]:assert u64(native_cb,offsets[ty])==wanted
 assert u64(native_cb,0x110)==cb['address'] and ivar(enc,'_commandBuffer')['raw_first_word']==cb['address']
 assert u64(push,40)==row['cursor_after']['state'] and u64(state,8)==row['device_cpp']['address']!=device_cpp
 assert u64(large,0x1e450)==backing[32]['GPU_address'];per_cb_state.append(row['device_cpp']['address'])
 assert row['retained_references'] and row['status']==0
 assert ivar(row['ended'],'_currentCommandEncoder')['raw_first_word']==0
 assert ivar(row['encoded'],'_currentCommandEncoder')['raw_first_word']==enc['address']
 data=read_snapshot(row['stream']);streams.append(data);packets=decode(data);hi=0;destination=0;uploads=[]
 for packet in packets:
  if packet.get('subchannel')!=1:continue
  for method,value in zip(packet.get('method_addresses',[]),packet.get('values',[])):
   if method=='0x188':hi=value
   if method=='0x18c':destination=(hi<<32)|value
  if packet.get('method')=='0x1b4':
   size=len(packet['values'])*4;owners=[k for k,b in backing.items() if b['GPU_address']<=destination and destination+size<=b['GPU_address']+b['length']];assert len(owners)==1 and owners[0] in [16,32]
   uploads.append({'destination_GPU_address':destination,'bytes':size,'queue_field_offset':owners[0]})
 records.append({'index':row['index'],'mode':row['mode'],'all_typed_pointer_cross_checks':True,'uploads':uploads})
assert len(set(per_cb_state))==3 and streams[0]==streams[2] and streams[1]!=streams[0]
life=json.loads((retention/'retention.json').read_text());assert not life['GPU_dispatch'] and not life['committed'] and life['driver_SHA256']==observed['driver_SHA256']
retained_count=unretained_count=0
for row in life['records']:
 retained=row['mode']=='retained';assert row['retained_references']==retained and row['status_before_release']==0
 held=row['while_command_buffer_held'];released=row['after_command_buffer_released'];assert held['queue'] and held['queue_QMD'] and held['params'] and released['params']
 for resource in ['output','counter','args']:assert held[resource]==retained and not released[resource]
 assert released['queue']==released['queue_QMD']
 if retained:retained_count+=1
 else:unretained_count+=1
assert retained_count==unretained_count==3
for directory in [root,retention]:
 process=json.loads((directory/'execution/manifest.json').read_text());assert process['exit_code']==0 and not process['SIGKILL_requested'] and not process['authoritative_ps_status']
 inputs=json.loads((directory/'inputs.json').read_text());source=directory/('native_resource_ownership.mm' if directory==root else 'native_retention_probe.mm');assert hashlib.sha256(source.read_bytes()).hexdigest()==inputs['source_SHA256']
summary={'status':'PASS','encoded_buffers_not_submitted':3,'live_queue_backing_buffers':5,'QMD_buffer_bytes':4096,'native_CB_backing_bytes':393216,'typed_Cpp_command_buffer_size':ct['size'],'distinct_per_command_states':3,'queue_backing_shared_across_commands':True,'retained_cases':retained_count,'unretained_negative_cases':unretained_count,'private_resources_kept_only_in_retained_cases':9,'private_weak_references_null_after_command_buffer':18,'GPU_dispatch':False,'ICB_implemented':False,'instantaneous_queue_release_guarantee':False,'shared_params_released':False,'scope':'Typed pointer/range agreement and bounded weak-reference lifetimes. The raw snapshot key device_cpp actually refers to State+8, a separate per-command dispatch state; real Device is State+0. Shared params remain alive and queue deallocation varies; no universal cache/destructor/replay claim.','records':records,'lifetime_records':life['records']}
(root/'independent-verification.json').write_text(json.dumps(summary,indent=2)+'\n');print(json.dumps({k:v for k,v in summary.items() if k not in ['records','lifetime_records']},indent=2))
