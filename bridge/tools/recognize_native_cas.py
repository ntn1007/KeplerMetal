#!/usr/bin/env python3
"""Conservative AIR+SM30 diagnosis, not a SASS-only or global compiler repair."""
from pathlib import Path
import argparse,hashlib,json,os,re,struct,subprocess,tempfile
ENVYDIS_SHA256='1c8730a9a4861f374c58407bff31d7ccb47a57eb23f9f82c6b3ea3deb079be0f'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify_decoder(code,text,decoder):
 """Regenerate the complete listing from the exact offline decoder, or refuse.

 This authenticates neither decoder correctness nor AIR semantics. The binary
 is snapshotted and verified before execution, with loader-injection variables
 removed. No GPU operation is performed.
 """
 if decoder is None or not isinstance(code,bytes) or not code or len(code)>1048576:return False
 try:
  executable=Path(decoder).read_bytes()
  if hashlib.sha256(executable).hexdigest()!=ENVYDIS_SHA256:return False
  with tempfile.TemporaryDirectory(prefix='kepler-cas-decoder-') as directory:
   tool=Path(directory)/'envydis'; source=Path(directory)/'program.sass'
   tool.write_bytes(executable);tool.chmod(0o500);source.write_bytes(code)
   if sha(tool)!=ENVYDIS_SHA256:return False
   env={k:v for k,v in os.environ.items() if not k.startswith(('DYLD_','LD_'))};env['LC_ALL']='C'
   run=subprocess.run([str(tool),'-m','gf100','-V','gk104','-i','-n',str(source)],capture_output=True,timeout=20,env=env)
   return run.returncode==0 and run.stdout==text.encode('utf-8') and sha(tool)==ENVYDIS_SHA256 and source.read_bytes()==code
 except (OSError,UnicodeError,subprocess.SubprocessError):return False
def register_references(op):
 """Every explicit GPR operand, including the full span of d/q operands."""
 refs=set()
 for base,suffix in re.findall(r'\$r(\d+)([dq]?)\b',op):
  start=int(base);refs.update(range(start,start+{'':1,'d':2,'q':4}[suffix]))
 return refs
def register_writes(op):
 """Conservative destinations for the decoded SM30 subset used here.
 None means an unqualified instruction, never presumed to preserve registers.
 """
 text=re.sub(r'^(?:\$p\d+ |\(not \$p\d+\) )','',op);opcode=text.split()[0]
 # JOIN is an instruction modifier: e.g. `join mov b32 $r9 $r6`
 # both reconverges and writes $r9. Do not discard the combined operation.
 if opcode=='join':
  body=text[len('join'):].strip()
  return register_writes(body) if body else None
 if opcode=='bar':return set() if re.fullmatch(r'bar popc \$p\d+ 0x[0-9a-f]+ 0x[0-9a-f]+ 0x[0-9a-f]+ 0x[0-9a-f]+',text) else None
 if opcode in {'bra','joinat','membar','nop','exit','st'}:return set()
 known={'mov','cvt','rcp','mul','add','sub','subr','xor','and','or','shl','shr','mad','fma','min','max','selp','slct','set','ld'}
 if opcode not in known:return None
 tokens=re.findall(r'\$[a-zA-Z]+\d*[dq]?',text)
 if not tokens:return None
 if opcode=='set' and tokens[0].startswith('$p'):return set()
 if opcode=='ld' and tokens[0].startswith('$p'):tokens=tokens[1:]
 if not tokens:return None
 m=re.fullmatch(r'\$r(\d+)([dq]?)',tokens[0])
 if not m:return None
 base=int(m[1]);width={'':1,'d':2,'q':4}[m[2]]
 return set(range(base,base+width))
def air_contract(module,function='test'):
 if len(module['functions'])!=1 or module['functions'][0]['name']!=function:return {'qualified':False,'reason':'One explicitly selected function required'}
 fn=module['functions'][0];ins=fn['instructions'];values=fn['values'];types=module['types']
 calls=[x for x in ins if x.get('callee','').startswith('air.atomic.local.cmpxchg.weak.i32')]
 if len(calls)!=1:return {'qualified':False,'reason':'Exactly one local uint32 weak CAS required'}
 call=calls[0];ret=types[call['type']];pointer=call['operands'][2];obj=types[values[call['operands'][1]]['type']];pt=types[values[pointer]['type']]
 if ret['kind']!=2 or ret['bits']!=32 or obj['kind']!=3 or obj['address_space']!=3 or pt['kind']!=3 or pt['address_space']!=0 or types[pt['element']]['bits']!=32:
  return {'qualified':False,'reason':'Unsupported AIR CAS ABI'}
 loads=[x for x in ins if x['index']>call['index'] and x['op']==14 and x['operands']==[pointer]]
 if len(loads)!=1:return {'qualified':False,'reason':'No unique post-CAS expected-pointer load; SASS is semantically ambiguous'}
 load=loads[0];insert=[x for x in ins if x['op']==5 and x['operands'][1]==load['value']]
 if load['block']!=call['block'] or any(x['block']!=call['block'] or x['op'] in (9,10,12,15,16) for x in ins[call['index']+1:load['index']]):
  return {'qualified':False,'reason':'Expected load is not on the same immediate unmodified post-CAS path'}
 if len(insert)!=1:return {'qualified':False,'reason':'Expected is not directly inserted into one output vector'}
 item=insert[0];idx=values[item['operands'][2]]
 # LLVM encodes scalar integer zero as AV_CNULL as well as AV_CINT.
 if idx['kind']==4 and types[idx['type']]['kind']==2 and idx['integer']==0:idx=dict(idx,kind=2)
 if idx['kind']!=2 or not 0<=idx['integer']<=3:return {'qualified':False,'reason':'Unsupported output component'}
 vector=types[item['type']]
 if vector['kind']!=4 or vector['count']!=4 or types[vector['element']]['bits']!=32:return {'qualified':False,'reason':'Only uint4 output is qualified'}
 byval={x['value']:x for x in ins};stores=[x for x in ins if x['op']==15 and x['index']>call['index']]
 reachable=[]
 for store in stores:
  value=store['operands'][1];seen=set()
  while value in byval and value not in seen:
   seen.add(value);node=byval[value]
   if value==item['value']:reachable.append(store);break
   if node['op']!=5:break
   if values[node['operands'][2]]['integer']==idx['integer']:break
   value=node['operands'][0]
 if len(reachable)!=1 or types[values[reachable[0]['operands'][0]]['type']]['address_space']!=1:
  return {'qualified':False,'reason':'No unique device output store preserving expected component'}
 store=reachable[0]
 # This recognizer has no dominance or cross-block data-flow model. Require
 # the whole observed output path to remain in the same straight-line block;
 # an SSA use in another block is not proof that every CAS path stores it.
 if not load['index']<item['index']<store['index'] or any(
    x['block']!=call['block'] or x['op'] in (8,9,10,12)
    for x in ins if load['index']<x['index']<=store['index']):
  return {'qualified':False,'reason':'Expected output is not on the same straight-line post-CAS path'}
 return {'qualified':True,'expected_output_component':idx['integer'],'CAS_instruction':call['index'],
         'expected_pointer_value':pointer,'expected_load_instruction':load['index'],'output_store_instruction':reachable[0]['index'],
         'scope':'Single local i32 weak CAS, direct post-call expected load to uint4 device output; broader CFG/alias/ABI cases rejected.'}
def sass_contract(code,text,component):
 if not isinstance(component,int) or isinstance(component,bool) or not 0<=component<=3:return {'qualified':False,'reason':'Unsupported output component'}
 if not code or len(code)%64:return {'qualified':False,'reason':'Unsupported schedule-block alignment'}
 instructions=[];next_offset=0
 for line in text.splitlines():
  m=re.match(r'^([0-9a-f]{8}): ([0-9a-f]{8}) ([0-9a-f]{8})\s+(.*)$',line)
  if not m:continue
  offset=int(m[1],16);raw=struct.pack('<II',int(m[2],16),int(m[3],16))
  if offset!=next_offset:return {'qualified':False,'reason':'Decoder offsets are missing, duplicated or out of order'}
  next_offset+=8
  if code[offset:offset+8]!=raw:return {'qualified':False,'reason':'Decoder bytes differ from original program'}
  op=re.sub(r'^B\s+','',m[4]).strip()
  if offset%64==0:
   if not op.startswith('sched '):return {'qualified':False,'reason':'Missing schedule word'}
   continue
  if '[unknown instruction]' in op or ('[unknown:' in op and not ('ld lock ' in op or 'st unlock ' in op) or '[unknown:' in op and '[unknown: 00000000 01000000]' not in op):
   return {'qualified':False,'reason':'Unsupported undecoded instruction/bits'}
  instructions.append((offset,op.split(' [unknown:')[0]))
 if next_offset!=len(code) or len(instructions)!=len(code)//8-len(code)//64:return {'qualified':False,'reason':'Decoder did not cover every original word'}
 # The floor applies to every lane of a vector operand, not only its base.
 max_reg=max((reg for _,op in instructions for reg in register_references(op)),default=0)
 if max_reg>=24:return {'qualified':False,'reason':'Register profile exceeds qualified floor24'}
 candidates=[]
 for i,(off,op) in enumerate(instructions):
  m=re.fullmatch(r'ld lock \$p(\d+) \$r(\d+) s\[(0x[0-9a-f]+|\$r[0-9]+)\]',op)
  if not m or i+4>=len(instructions):continue
  pred,old,addr=m.groups();old=int(old)
  eq=re.fullmatch(r'\$p'+pred+r' set b32 \$r(\d+) eq s32 \$r'+str(old)+r' \$r(\d+)',instructions[i+1][1])
  if not eq:continue
  temp,cmp=map(int,eq.groups())
  sel=re.fullmatch(r'\$p'+pred+r' slct b32 \$r(\d+) \$r(\d+) \$r'+str(old)+r' ne s32 \$r'+str(temp),instructions[i+2][1])
  if not sel:continue
  update,replacement=map(int,sel.groups())
  if temp in [old,cmp] or update in [old,cmp] or old==cmp:continue
  # A register-indexed shared address must survive every write in the lock
  # loop. The exact same operand is required on the unlock; per-shader GPU
  # qualification is still needed to establish the input's address bounds.
  if addr.startswith('$r'):
   address_register=int(addr[2:])
   if address_register>=24 or address_register in (old,cmp,temp,update):continue
  unlock=re.fullmatch(r'\$p'+pred+r' st unlock \$p(\d+) s\['+re.escape(addr)+r'\] \$r'+str(update),instructions[i+3][1])
  if not unlock or instructions[i+4][1]!='(not $p'+unlock[1]+') bra '+hex(off):continue
  late=[]
  for j in range(i+5,len(instructions)-1):
   bo,bop=instructions[j]
   if re.fullmatch(r'set \$p\d+ 0x1 eq [us]32 \$r'+str(cmp)+r' \$r'+str(old),bop):late.append(j)
  if len(late)!=1:continue
  j=late[0];patch,patchop=instructions[j+1]
  # The value copied must still be the ld-lock result. A later comparison
  # of the same register numbers is insufficient if either was redefined.
  valid_live=True
  for _,operation in instructions[i+5:j]:
   writes=register_writes(operation)
   if writes is None or writes & {old,cmp}:valid_live=False;break
  if not valid_live:continue
  if patchop!='membar cta' or struct.unpack_from('<Q',code,patch)[0]!=0xe000000000001c05:continue
  stores=[]
  for k in range(j+2,len(instructions)):
   so,sop=instructions[k];sm=re.fullmatch(r'st b128 wb g\[\$r(\d+)d\] \$r(\d+)q',sop)
   if sm:stores.append((k,int(sm[1]),int(sm[2])))
  if len(stores)!=1:continue
  k,address_base,base=stores[0]
  if cmp!=base+component or address_base<=cmp<address_base+2:continue
  # The repair changes cmp. Reject any other explicit use or definition after
  # the redirect, even after the store; it could change an unrelated result or
  # a memory address. This is deliberately stricter than a liveness analysis.
  other_use=False
  for n,(_,op2) in enumerate(instructions[j+2:],start=j+2):
   if n!=k and (register_writes(op2) is None or cmp in register_references(op2)):
    other_use=True;break
  if other_use:continue
  edges=[(source,int(target,16)) for source,op2 in instructions for target in re.findall(r'(?:bra|joinat) (0x[0-9a-f]+)',op2)]
  # Decoder branch targets may identify a schedule word rather than the next
  # executable instruction. Apply the same normalization as the flow tracer.
  edges=[(source,target+8 if target%64==0 else target) for source,target in edges]
  targets=[target for _,target in edges]
  if patch in targets or patch+8 in targets:continue
  branches=[]
  for source,operation in instructions:
   branch=re.fullmatch(r'(?:(?:\$p\d+|\(not \$p\d+\)) )?bra (0x[0-9a-f]+)',operation)
   if branch:
    target=int(branch[1],16);branches.append((source,target+8 if target%64==0 else target))
  comparison=instructions[j][0];retry=instructions[i+4][0]
  # No direct branch may enter after ld-lock from outside the matched region,
  # or re-enter the fixed lock/unlock sequence without the ld-lock itself.
  if any(off<target<=comparison and not off<=source<=comparison for source,target in branches):continue
  if any(off<target<=retry for _,target in branches):continue
  # A path that entered the lock region must not jump past the redirect;
  # otherwise it could reach an output without receiving the repair.
  if any(off<=source<patch and target>patch for source,target in branches):continue
  # Reconvergence is not an ordinary direct branch. Keep the one observed
  # scoped shape as an explicit assumption: a single joinat before ld-lock
  # resumes immediately after the join following the retry. Reject any other
  # target entering the lock-to-comparison interval, including schedule words.
  reconvergence=[]
  for source,operation in instructions:
   match=re.fullmatch(r'(?:(?:\$p\d+|\(not \$p\d+\)) )?joinat (0x[0-9a-f]+)',operation)
   if match:
    target=int(match[1],16);target=target+8 if target%64==0 else target
    if off<target<=comparison:reconvergence.append((source,target))
  if reconvergence:
   if i+6>=len(instructions) or instructions[i+5][1]!='join nop':continue
   assumed_entry=instructions[i+6][0]
   if len(reconvergence)!=1 or reconvergence[0][0]>=off or reconvergence[0][1]!=assumed_entry:continue
  # A post-patch backedge can re-enter the lock/compare region after cmp has
  # been changed. Refuse even if the path is unreachable or conditionally safe;
  # this structural check does not establish complete control-flow semantics.
  if any(source>patch and target<=patch for source,target in edges):continue
  candidates.append({'qualified':True,'old_register':old,'expected_register':cmp,'shared_address':addr,
    'CAS_load_offset':off,'success_compare_offset':instructions[j][0],'redirect_offset':patch,'return_offset':patch+8,
    'output_store_offset':instructions[k][0],'output_vector_base':base,'expected_output_component':component,
    'max_explicit_register':max_reg,'unknown_lock_modifier_preserved':'0x01000000'})
 if len(candidates)!=1:return {'qualified':False,'reason':'No unique safe structural CAS/output pattern'}
 return candidates[0]
def recognize(directory,decoder=None):
 d=Path(directory);names=['test.metal','test.air','test.metallib','typed-air.json','native.sass','native.asm']
 snapshot={name:(d/name).read_bytes() for name in names};air=air_contract(json.loads(snapshot['typed-air.json']))
 code=snapshot['native.sass'];listing=snapshot['native.asm'].decode('utf-8');verified=verify_decoder(code,listing,decoder)
 sass=sass_contract(code,listing,air.get('expected_output_component',0)) if verified else {'qualified':False,'reason':'Offline decoder missing, unpinned or listing differs'}
 return {'policy_version':1,'qualified':air['qualified'] and verified and sass['qualified'],'AIR':air,'SASS':sass,'decoder_reproduced_listing':verified,
         'hashes':{name:hashlib.sha256(value).hexdigest() for name,value in snapshot.items()},
         'SASS_only_repair_forbidden':True,'scope':'Offline candidate diagnosis plus exact input fingerprints; per-shader GPU qualification required before use.'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--decoder',type=Path,required=True);a=p.parse_args();r=recognize(a.input,a.decoder)
 (a.input/'recognition.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
