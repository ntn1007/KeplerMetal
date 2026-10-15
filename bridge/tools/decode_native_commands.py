#!/usr/bin/env python3
"""Decode bounded captured GF100+ FIFO packets without executing them.
Format reference: Envytools demmt/pushbuf.c, pinned f102b82381f3f11cee113d16374c87091db039d9.
"""
from pathlib import Path
import argparse,hashlib,json,struct
def decode(data):
 if len(data)%4:raise ValueError('Unaligned packet stream')
 words=struct.unpack('<'+str(len(data)//4)+'I',data);offset=0;packets=[]
 while offset<len(words):
  start=offset;header=words[offset];offset+=1
  if not header:packets.append({'offset':start*4,'kind':'NOP','bytes':4});continue
  mode=header>>29;method=(header&0x1fff)*4;subchannel=(header>>13)&7;count=(header>>16)&0x1fff
  if mode==4:
   values=[count];addresses=[method];kind='immediate'
  else:
   if mode not in [1,3,5] or not count or count>len(words)-offset:raise ValueError('Unqualified/truncated packet at '+hex(start*4))
   values=list(words[offset:offset+count]);offset+=count;kind={1:'incrementing',3:'constant',5:'one_increment'}[mode]
   addresses=[method+(4*i if mode==1 else 4 if mode==5 and i else 0) for i in range(count)]
  packets.append({'offset':start*4,'header':hex(header),'kind':kind,'subchannel':subchannel,'method':hex(method),'bytes':(offset-start)*4,
                  'method_addresses':[hex(x) for x in addresses],'values':values})
 return packets
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);a=p.parse_args();root=a.input.resolve();capture=json.loads((root/'capture.json').read_text());records=[]
 for record in capture['records']:
  path=Path(record['file']);data=path.read_bytes();assert hashlib.sha256(data).hexdigest()==record['SHA256'] and len(data)==record['bytes'];packets=decode(data);assert sum(p['bytes'] for p in packets)==len(data)
  upload_state={};uploads=[]
  for packet in packets:
   for addr,value in zip(packet.get('method_addresses',[]),packet.get('values',[])):
    method=int(addr,16)
    if packet.get('subchannel')==1 and method in [0x180,0x184,0x188,0x18c,0x1b0]:upload_state[method]=value
   if packet.get('subchannel')==1 and packet.get('method')=='0x1b4':
    target=(upload_state.get(0x188,0)<<32)|upload_state.get(0x18c,0);payload=struct.pack('<'+str(len(packet['values']))+'I',*packet['values']);name=f"{record['mode']}-{record['step']}-upload-{len(uploads)}.bin";(root/name).write_bytes(payload)
    uploads.append({'packet_offset':packet['offset'],'destination_GPU_address':target,'line_bytes':upload_state.get(0x180),'data_bytes':len(payload),'payload_file':str(root/name),
                    'SHA256':hashlib.sha256(payload).hexdigest()})
  address=capture['args_GPU_address']+capture['indirect_byte_offset'];hi,lo=address>>32,address&0xffffffff;w=struct.unpack('<'+str(len(data)//4)+'I',data)
  pairs=[i*4 for i in range(len(w)-1) if (w[i],w[i+1]) in [(hi,lo),(lo,hi)]]
  records.append({'mode':record['mode'],'step':record['step'],'stream_SHA256':record['SHA256'],'packets':packets,'uploads':uploads,'indirect_argument_address_matches':pairs})
  print(record['mode'],record['step'],'bytes',len(data),'packets',len(packets),'uploads',[(u['line_bytes'],u['data_bytes']) for u in uploads],'args-address matches',pairs)
 summary={'status':'PASS','GPU_dispatch':False,'native_memory_modified':False,'records':records,
          'scope':'Packet framing and upload identification against pinned public register definitions; no replay, no ICB implementation, other payload meanings remain unqualified.'}
 (root/'decoded-packets.json').write_text(json.dumps(summary,indent=2)+'\n')
