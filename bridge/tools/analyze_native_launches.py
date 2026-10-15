#!/usr/bin/env python3
"""Match uploads and launches using pinned GK104 descriptor/register definitions."""
from pathlib import Path
import argparse,hashlib,json,struct
p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output-name',default='launches.json');a=p.parse_args();root=a.input.resolve();assert Path(a.output_name).name==a.output_name;records=json.loads((root/'decoded-packets.json').read_text())['records'];rows=[]
for record in records:
 descriptors={}
 for upload in record['uploads']:
  if upload['data_bytes']!=256:continue
  data=Path(upload['payload_file']).read_bytes();w=lambda o:struct.unpack_from('<I',data,o)[0]
  cb=[]
  for slot in range(8):
   low=w(0x74+slot*8);high=w(0x78+slot*8)
   # GK104 CB_CONFIG_1.SIZE bits31:15 encode bytes, including 0x10000.
   # The low address alignment is 256 bytes; it is not a size multiplier.
   cb.append({'slot':slot,'enabled':bool(w(0x50)&(1<<slot)),'GPU_address':((high&255)<<32)|low,'bytes':high>>15})
  qmd={'GPU_address':upload['destination_GPU_address'],'program_start':hex(w(0x20)),'grid':[w(0x30)&0x7fffffff,w(0x34)&65535,w(0x34)>>16],
       'block':[w(0x48)>>16,w(0x4c)&65535,w(0x4c)>>16],'GPR':(w(0xb8)>>24)&63,'shared_bytes':w(0x44)&65535,'CB':cb,
       'payload_SHA256':hashlib.sha256(data).hexdigest()};descriptors[qmd['GPU_address']]=qmd
 launches=[];selected=None
 for packet in record['packets']:
  if packet.get('subchannel')!=1:continue
  if packet.get('method')=='0x2b4':selected=packet['values'][0]<<8
  if packet.get('method')=='0x2bc':
   assert selected in descriptors;launches.append({'packet_offset':packet['offset'],'launch_value':packet['values'][0],'descriptor':descriptors[selected]})
 assert len(launches)==(1 if record['mode']=='direct' else 2)
 if record['mode']=='direct':assert launches[0]['descriptor']['grid']==[3,1,1] and launches[0]['descriptor']['block']==[32,1,1]
 else:
  assert launches[0]['descriptor']['grid']==[1,1,1] and launches[0]['descriptor']['block']==[1,1,1]
  assert launches[1]['descriptor']['grid']==[0,0,0] and launches[1]['descriptor']['block']==[32,1,1]
 rows.append({'mode':record['mode'],'step':record['step'],'launches':launches,'indirect_arguments_byte_matches':record['indirect_argument_address_matches']})
summary={'status':'PASS','GPU_dispatch':False,'rows':rows,'CB_size_unit':'bytes (CB_CONFIG_1 bits31:15), corrected from initial erroneous x256 decode','scope':'Read-only CPU encoding snapshot: direct has one descriptor, indirect schedules an internal helper then user descriptor with zero placeholder grid. Hardware descriptor writes/effects are inferred, not observed by this snapshot; prior GPU indirect tests validate final geometry.'}
(root/a.output_name).write_text(json.dumps(summary,indent=2)+'\n')
for r in rows:print(r['mode'],r['step'],[(l['descriptor']['program_start'],l['descriptor']['grid'],l['descriptor']['GPR']) for l in r['launches']])
