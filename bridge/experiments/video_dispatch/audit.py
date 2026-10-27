#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare pinned, on-disk Sierra and current NVIDIA video dispatch evidence.

No candidate, private entry, GPU command, or selector is executed. Vtable and
kernel file observations do not identify the active live dispatch.
"""
import argparse,hashlib,json,pathlib,re,struct,subprocess,sys
P=pathlib.Path(__file__).resolve().parents[2]
B=None
ROOT=USER=SEL=OLD=HEADER=None
PUBLIC=P/'tools'
CURRENT=pathlib.Path('/System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce')
IO=pathlib.Path('/System/Library/Extensions/IOAcceleratorFamily2.kext/Contents/MacOS/IOAcceleratorFamily2')
PINS={}
# Function addresses, symbol-name fragments, raw flags and counts from the
# exact Sierra image. Names/count interpretation is limited by the historical ABI.
EXPECTED=[(0x5ea02,'get_decoder_config',0,0,1),(0x5ea20,'set_source_size',4,0,0xffffffff),(0x5ea7c,'get_3d_config',0,0,1),(0x5ea9a,'get_fb_config',0,0,1),(0x5eaf4,'check_acc_cap',0,0,1),(0x5eb02,'acquire_channel',0,1,2),(0x5eccc,'map_texture',4,1,0),(0x5ed92,'cipher_initiate',3,256,280),(0x5ee0c,'cipher_query',2,0,280),(0x5ee84,'store_session_key',4,1,0xffffffff),(0x5ef3e,'retrieve_session_key',2,1,0xffffffff),(0x5efe0,'instance_ctrl',0,2,1),(0x5f27c,'get_texture_params',2,1,24)]


def check(ok,msg):
 if not ok:raise ValueError(msg)
def sha(b):return hashlib.sha256(b).hexdigest()
def readpin(path,digest):
 d=path.read_bytes();check(sha(d)==digest,'pinned input changed: '+str(path));return d

def validate_table(raw,symbols):
 check(len(raw)==13*48 and sha(raw)=='3bdc9e41de2acbfd05d3f11670bedc5098fa0979d009c1bdb6ce12603998c2d0','historical method table')
 rows=[]
 for idx,(target,fragment,flags,count0,count1) in enumerate(EXPECTED):
  values=struct.unpack_from('<6Q',raw,idx*48)
  check(values==(0,target,0,flags,count0,count1),'entry changed '+hex(0x100+idx))
  candidates=[s['name'] for s in symbols if s['value']==target and s['name'].startswith('__ZN14nvVideoContext') and fragment in s['name']]
  check(len(candidates)==1,'function symbol ambiguous '+hex(target))
  rows.append({'selector':hex(0x100+idx),'function_address':hex(target),'function_name':fragment,'flags':flags,'count0':count0,'count1':count1})
 return rows

def rea(path,address,digest):
 d=json.loads(path.read_text())['result']['structuredContent']
 check(d['subject']['digest']['sha256']==digest and d['operation']=='analyze_function' and d['parameters']['procedure']==address and d['raw_result']['value']['procedure']['address']==address,'REA subject '+address)
 return d['evidence_id'],d['raw_result']['value']['pseudocode']

def validate_instructions(rows,checks):
 for address,pattern in checks.items():check(address in rows and re.search(pattern,rows[address]) is not None,'instruction differs '+hex(address))

def disassemble(path,start,end):
 result=subprocess.run(['xcrun','llvm-objdump','-d','--start-address='+hex(start),'--stop-address='+hex(end),str(path)],capture_output=True,text=True,timeout=30,check=True)
 rows={}
 for line in result.stdout.splitlines():
  match=re.match(r'^\s*([0-9a-fA-F]+):\s+(?:(?:[0-9a-fA-F]{2})\s+)+(.+)$',line)
  if match:
   address=int(match.group(1),16);check(start<=address<end and address not in rows,'invalid disassembly');rows[address]=re.sub(r'\s+',' ',match.group(2).split('##')[0].strip())
 check(start in rows,'function entry missing');return rows

def audit():
 data={p:readpin(p,h) for p,h in PINS.items()};sys.path.insert(0,str(PUBLIC));from compare_video_profile import file_bytes,symbols_and_external_relocations

 old=data[OLD];now=data[CURRENT];io=data[IO]
 oldsym,oldrel=symbols_and_external_relocations(old);newsym,newrel=symbols_and_external_relocations(now);_,iorel=symbols_and_external_relocations(io)
 def sym(items,name):
  a=[x for x in items if x['name']==name];check(len(a)==1,'symbol missing '+name);return a[0]['value']
 check(sym(oldsym,'__ZTV14nvVideoContext')==0x87df0 and sym(newsym,'__ZTV14nvVideoContext')==0x90fe8,'vtable identity')
 check(sym(oldsym,'__ZZN14nvVideoContext12contextStartEvE11methodDescs')==0x88a30,'table symbol')
 check(sym(oldsym,'__ZN14nvVideoContext26getTargetAndMethodForIndexEPP9IOServicej')==0x5f59e,'historical override')
 check(not any(x['name']=='__ZN14nvVideoContext26getTargetAndMethodForIndexEPP9IOServicej' for x in newsym),'current explicit override unexpectedly present')
 _,raw=file_bytes(old,0x88a30,13*48);rows=validate_table(raw,oldsym)
 _,oldptr=file_bytes(old,0x87df0+0x950,8);check(struct.unpack('<Q',oldptr)[0]==0x5f59e and 0x88740 not in oldrel,'old vtable target')
 key=0x90fe8+0x950;v=newrel.get(key,[]);check(len(v)==1 and v[0]['symbol']['name']=='__ZN15IOAccelContext226getTargetAndMethodForIndexEPP9IOServicej' and v[0]['external']==1 and v[0]['length_code']==3 and v[0]['type']==0,'current inherited target relocation')
 v=newrel.get(0x90fe8+0x860,[]);check(len(v)==1 and v[0]['symbol']['name'].startswith('__ZN15IOAccelContext214externalMethod'),'current externalMethod relocation')
 v=iorel.get(0x73250,[]);check(len(v)==1 and v[0]['symbol']['name'].startswith('__ZN12IOUserClient14externalMethod'),'IOAccelerator fallback relocation')
 validate_instructions(disassemble(OLD,0x5f59e,0x5f5de),{0x5f5ae:r'leal -0x100\(%rdx\), %eax',0x5f5b4:r'cmpl \$0xc, %eax',0x5f5b7:r'ja 0x5f5cf',0x5f5be:r'leaq \(%rax,%rax,2\), %rax',0x5f5c2:r'shlq \$0x4, %rax'})
 validate_instructions(disassemble(IO,0x860a,0x8655),{0x862d:r'cmpl \$0x7, %edx',0x8630:r'ja 0x8648',0x8648:r'xorl %eax, %eax'})
 h=data[HEADER].decode();check('struct IOExternalMethod {' in h and 'IOMethod            func;' in h and 'IOByteCount         count0;' in h and 'kIOUCScalarIScalarO = 0' in h,'XNU header')
 old_id,oldcode=rea(ROOT/'0x5f59e.private.json','0x5f59e',PINS[OLD]);start_id,startcode=rea(ROOT/'0x5e94a.private.json','0x5e94a',PINS[OLD]);channel_id,channel=rea(ROOT/'0x5eb02.private.json','0x5eb02',PINS[OLD])
 check('param_3 - 0x100U' in oldcode and '* 0x30' in oldcode and 'methodDescs' in startcode and 'nvChannelManager14AcquireChannel' in channel,'historical REA evidence')
 client_id,client=rea(USER/'0x2e27c.private.json','0x2e27c','bf2110a8a74786fe06da672e35f05a0dbd554aa651a83bacf02753c5899ef567')
 check('_IOAccelVideoContextCreate' in client and '_IOConnectCallScalarMethod' in client and '0x105,&local_38,1,local_48,&local_4c' in client,'provider 0x105 call evidence')
 evidence=[]
 for addr,selector in [('0x2e526','0x105'),('0x2e604','0x100'),('0x2e66e','0x102'),('0x2e6d8','0x103'),('0x2e774','0x104'),('0x2e808','0x106'),('0x2eb42','0x10b')]:
  id,pseudo=rea(SEL/(addr+'.private.json'),addr,'bf2110a8a74786fe06da672e35f05a0dbd554aa651a83bacf02753c5899ef567')
  check('_IOConnectCallScalarMethod' in pseudo and selector in pseudo,'selector evidence '+addr);evidence.append({'function':addr,'selector':selector,'evidence_id':id})
 return {'status':'STATIC_DISPATCH_COMPARISON_PASS','historical_GeForce_SHA256':PINS[OLD],'current_GeForce_SHA256':PINS[CURRENT],'current_IOAccelerator_SHA256':PINS[IO],'historical_table_SHA256':sha(raw),'historical_vtable_lookup':'0x5f59e','current_vtable_lookup':'IOAccelContext2::getTargetAndMethodForIndex (external relocation)','current_base_static_index_max':7,'historical_entries':rows,'historical_provider_selector_0x105':'one scalar input and two scalar outputs; function called acquire_channel in Sierra symbols','provider_REA':evidence,'other_REA_evidence_ids':[old_id,start_id,channel_id,client_id],'hardware_execution_proved':False,'limits':['Static disk image evidence only; no live kernel bytes or live vtable checked.','Current base lookup above 7 and old override difference do not by themselves prove every live externalMethod dispatch takes this path.','The XNU header is a published modern comparison, not proof of the exact Sierra ABI.','Opening a video context does not establish command submission or decoding.','No private video selector or hardware command was called.']}
def main():
 global B,ROOT,USER,SEL,OLD,HEADER,PINS
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--lab',type=pathlib.Path,required=True);p.add_argument('--out',type=pathlib.Path,required=True);a=p.parse_args()
 B=a.lab.resolve();ROOT=B/'results/video-sierra-kernel-contract-20261027-01';USER=B/'results/video-sierra-provider-20261027-01';SEL=B/'results/video-sierra-selectors-20261027-01';OLD=ROOT/'System/Library/Extensions/GeForce.kext/Contents/MacOS/GeForce';HEADER=B/'results/video-rm-abi-progress-20261018/public-references/xnu/IOUserClient.h'
 PINS={OLD:'25a0bccd7caa884d6aa964743b35f879ec326c46d255dc6212c47e7a20f6f38e',CURRENT:'44f131a958d48afd6ab675a851330c37506557c9d499484170c886c3731bdbb3',IO:'37e563d6cf3626101f30b1727a4f60dec02152dff9c74c0269c30c213a7320c8',HEADER:'01c419c05d471eac01292153afb650dd6abfccd30e0cc3b48ad8ffe6e7793cf9',PUBLIC/'compare_video_profile.py':'3f0e6b796f90de5f7a578dd9abe6fc924530ad2853086ef8c583990953ac0506'}
 check(not a.out.exists() and a.out.parent.is_dir(),'fresh output required')
 evidence_pins={
  ROOT/'0x5f59e.private.json':'d38d997fe407f4fc8efd8868acab243b554cbbd329f2743a8a76ed6b7dcc1b2c',
  ROOT/'0x5e94a.private.json':'37c791ad74794a7a018be957588dd896aca5526e274d5932b072c229ccf4863f',
  ROOT/'0x5eb02.private.json':'9b0c916f3fd9a37ff65bf597c2b17c5b22e4060f86ba05e8f9ebfcee3fe1041f',
  USER/'0x2e27c.private.json':'0d030d0040bf4c115aea1a0733f9880bbdef1014f394c6094f94bd26a10c2a8d',
  SEL/'0x2e526.private.json':'d458593a41cde52fa3838ca8bb742e2f7a2b2640af54158ea2ed5090cd48ebe8',
  SEL/'0x2e604.private.json':'7a14cc16449a1203e573a447dbd6c1a219f6d71b64de1b6ed616d7e6151a63b6',
  SEL/'0x2e66e.private.json':'1b8a041a1f2e3dfe0d7d90c529787937c50657deab672d4e367143e23c77b176',
  SEL/'0x2e6d8.private.json':'4cea58c0dda16291709e0aef7febaf77999a36425dc046773b87d8c1861191ff',
  SEL/'0x2e774.private.json':'25af16733fee785eb0c1bcca00d825f9e2d7b9734e74fb70ed2f8de50c52dfa6',
  SEL/'0x2e808.private.json':'4988597c791141471ae126055004106d161a31c63e3770f7e9e63f939c68482d',
  SEL/'0x2eb42.private.json':'c7b05acb6b123a5373ca3a66b7935b26998bac0af8426296b966f5bcb693b24a'}
 for path,digest in evidence_pins.items():readpin(path,digest)

 report=audit()
 sys.path.insert(0,str(PUBLIC));from compare_video_profile import file_bytes,symbols_and_external_relocations
 data=OLD.read_bytes();_,raw=file_bytes(data,0x88a30,13*48);symbols,_=symbols_and_external_relocations(data)
 cases=[]
 for name,b,s in [('changed-byte',bytes([raw[0]^1])+raw[1:],symbols),('missing-symbol',raw,[x for x in symbols if x['value']!=0x5eb02])]:
  try:validate_table(b,s)
  except ValueError:cases.append(name)
  else:raise ValueError('negative control unexpectedly passed: '+name)
 report['negative_controls_rejected']=cases;report['native_execution']=False;report['pinned_REA_records']=len(evidence_pins)
 with a.out.open('x') as f:json.dump(report,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps({'status':report['status'],'negative_controls_rejected':cases,'hardware_execution_proved':False}))
if __name__=='__main__':main()
