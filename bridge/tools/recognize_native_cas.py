#!/usr/bin/env python3
"""Conservative AIR+SM30 diagnosis, not a SASS-only or global compiler repair."""
from pathlib import Path
import argparse,hashlib,json,re,struct
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def register_writes(op):
 """Conservative destinations for the decoded SM30 subset used here.
 None means an unqualified instruction, never presumed to preserve registers.
 """
 text=re.sub(r'^(?:\$p\d+ |\(not \$p\d+\) )','',op);opcode=text.split()[0]
 if opcode=='bar':return set() if re.fullmatch(r'bar popc \$p\d+ 0x[0-9a-f]+ 0x[0-9a-f]+ 0x[0-9a-f]+ 0x[0-9a-f]+',text) else None
 if opcode in {'bra','join','joinat','membar','nop','exit','st'}:return set()
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
 if idx['kind']!=2 or idx['integer']>3:return {'qualified':False,'reason':'Unsupported output component'}
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
 return {'qualified':True,'expected_output_component':idx['integer'],'CAS_instruction':call['index'],
         'expected_pointer_value':pointer,'expected_load_instruction':load['index'],'output_store_instruction':reachable[0]['index'],
         'scope':'Single local i32 weak CAS, direct post-call expected load to uint4 device output; broader CFG/alias/ABI cases rejected.'}
def sass_contract(code,text,component):
 if not code or len(code)%64:return {'qualified':False,'reason':'Unsupported schedule-block alignment'}
 instructions=[]
 for line in text.splitlines():
  m=re.match(r'^([0-9a-f]{8}): ([0-9a-f]{8}) ([0-9a-f]{8})\s+(.*)$',line)
  if not m:continue
  offset=int(m[1],16);raw=struct.pack('<II',int(m[2],16),int(m[3],16))
  if code[offset:offset+8]!=raw:return {'qualified':False,'reason':'Decoder bytes differ from original program'}
  op=re.sub(r'^B\s+','',m[4]).strip()
  if offset%64==0:
   if not op.startswith('sched '):return {'qualified':False,'reason':'Missing schedule word'}
   continue
  if '[unknown instruction]' in op or ('[unknown:' in op and not ('ld lock ' in op or 'st unlock ' in op) or '[unknown:' in op and '[unknown: 00000000 01000000]' not in op):
   return {'qualified':False,'reason':'Unsupported undecoded instruction/bits'}
  instructions.append((offset,op.split(' [unknown:')[0]))
 if len(instructions)!=len(code)//8-len(code)//64:return {'qualified':False,'reason':'Decoder did not cover every original word'}
 max_reg=max((int(x) for _,op in instructions for x in re.findall(r'\$r(\d+)',op)),default=0)
 if max_reg>=24:return {'qualified':False,'reason':'Register profile exceeds qualified floor24'}
 candidates=[]
 for i,(off,op) in enumerate(instructions):
  m=re.fullmatch(r'ld lock \$p(\d+) \$r(\d+) s\[(0x[0-9a-f]+)\]',op)
  if not m or i+4>=len(instructions):continue
  pred,old,addr=m.groups();old=int(old)
  eq=re.fullmatch(r'\$p'+pred+r' set b32 \$r(\d+) eq s32 \$r'+str(old)+r' \$r(\d+)',instructions[i+1][1])
  if not eq:continue
  temp,cmp=map(int,eq.groups())
  sel=re.fullmatch(r'\$p'+pred+r' slct b32 \$r(\d+) \$r(\d+) \$r'+str(old)+r' ne s32 \$r'+str(temp),instructions[i+2][1])
  if not sel:continue
  update,replacement=map(int,sel.groups())
  if temp in [old,cmp] or update in [old,cmp] or old==cmp:continue
  unlock=re.fullmatch(r'\$p'+pred+r' st unlock \$p(\d+) s\['+addr+r'\] \$r'+str(update),instructions[i+3][1])
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
   so,sop=instructions[k];sm=re.fullmatch(r'st b128 wb g\[\$r\d+d\] \$r(\d+)q',sop)
   if sm:stores.append((k,int(sm[1])))
  if len(stores)!=1:continue
  k,base=stores[0]
  if cmp!=base+component:continue
  # Comparand must survive untouched to the vector store. Other instructions
  # may use it; they must not redefine it or enter the patch through an edge.
  overwrite=False
  for _,op2 in instructions[j+2:k]:
   writes=register_writes(op2)
   if writes is None or cmp in writes:overwrite=True
  if overwrite:continue
  targets=[int(x,16) for _,op2 in instructions for x in re.findall(r'(?:bra|joinat) (0x[0-9a-f]+)',op2)]
  if patch in targets or patch+8 in targets:continue
  candidates.append({'qualified':True,'old_register':old,'expected_register':cmp,'shared_address':addr,
    'CAS_load_offset':off,'success_compare_offset':instructions[j][0],'redirect_offset':patch,'return_offset':patch+8,
    'output_store_offset':instructions[k][0],'output_vector_base':base,'expected_output_component':component,
    'max_explicit_register':max_reg,'unknown_lock_modifier_preserved':'0x01000000'})
 if len(candidates)!=1:return {'qualified':False,'reason':'No unique safe structural CAS/output pattern'}
 return candidates[0]
def recognize(directory):
 d=Path(directory);air=air_contract(json.loads((d/'typed-air.json').read_text()))
 code=(d/'native.sass').read_bytes();sass=sass_contract(code,(d/'native.asm').read_text(),air.get('expected_output_component',0))
 return {'policy_version':1,'qualified':air['qualified'] and sass['qualified'],'AIR':air,'SASS':sass,
         'hashes':{p.name:sha(p) for p in [d/'test.metal',d/'test.air',d/'test.metallib',d/'typed-air.json',d/'native.sass',d/'native.asm']},
         'SASS_only_repair_forbidden':True,'scope':'Offline candidate diagnosis plus exact input fingerprints; per-shader GPU qualification required before use.'}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);a=p.parse_args();r=recognize(a.input)
 (a.input/'recognition.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
