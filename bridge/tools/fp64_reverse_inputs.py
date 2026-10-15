"""Raw binary64 inputs and integer-only conversion/rounding reference."""
import math,struct

MODES=('rn','rz','rp','rm')
OPS=tuple(f'to_{target}_{mode}' for target in ('f32','i64','u64') for mode in MODES)
MASK=(1<<64)-1
bits=lambda x:struct.unpack('<Q',struct.pack('<d',x))[0]
BASE_EDGES=[0,1<<63,1,(1<<63)|1,0x0010000000000000,0x000fffffffffffff,
 0x7fefffffffffffff,0xffefffffffffffff,0x7ff0000000000000,0xfff0000000000000,
 0x7ff8000000000042,0xfff8000000000042,0x7ff0000000000001,0xfff0000000000001]
for value in (0.1,0.5,1.,1.5,2.5,3.5,1.+2.**-24,2.**-149,2.**-150,2.**-126,
              (2.-2.**-23)*2.**127,(2.-2.**-24)*2.**127,2.**52,2.**53,2.**63,2.**64):
 word=bits(value)
 for adjacent in (word-1,word,word+1):BASE_EDGES.extend((adjacent,adjacent|(1<<63)))

def columns(op,local,count,trial):
 assert op in OPS and local in (32,128,1024) and trial in (0,1,2)
 state=0x880d20261014+97*local+104729*trial;result=[[],[],[]]
 for i in range(count):
  for col in range(3):
   state=(state*6364136223846793005+1442695040888963407)&MASK
   result[col].append(BASE_EDGES[(i+trial*37)%len(BASE_EDGES)] if col==0 and i<len(BASE_EDGES) else state)
 return result

def rounded(magnitude,shift,mode,negative):
 if shift<=0:return magnitude<<-shift
 integer=magnitude>>shift;remainder=magnitude&((1<<shift)-1)
 if mode=='rn':
  halfway=1<<(shift-1);increment=remainder>halfway or (remainder==halfway and integer&1)
 elif mode=='rz':increment=False
 elif mode=='rp':increment=not negative and remainder!=0
 else:increment=negative and remainder!=0
 return integer+int(increment)

def binary64_to_binary32(raw,mode):
 negative=bool(raw>>63);sign=int(negative)<<31;exp=(raw>>52)&2047;fraction=raw&((1<<52)-1)
 if exp==2047:return sign|0x7f800000|(((fraction>>29)|(1<<22)) if fraction else 0)
 if exp==0 and fraction==0:return sign
 magnitude=fraction|((1<<52) if exp else 0);power=exp-1023-52 if exp else -1074
 exponent=magnitude.bit_length()-1+power
 if exponent < -126:return sign|rounded(magnitude,-(power+149),mode,negative)
 significand=rounded(magnitude,magnitude.bit_length()-24,mode,negative)
 if significand==1<<24:significand>>=1;exponent+=1
 if exponent>127:
  infinity=mode=='rn' or (mode=='rp' and not negative) or (mode=='rm' and negative)
  return sign|(0x7f800000 if infinity else 0x7f7fffff)
 return sign|((exponent+127)<<23)|(significand&0x7fffff)

def expected_bits(op,raw):
 target,mode=op.split('_')[1:];assert mode in MODES
 if target=='f32':return binary64_to_binary32(raw,mode)
 negative=bool(raw>>63);exp=(raw>>52)&2047;fraction=raw&((1<<52)-1)
 lower=-(1<<63) if target=='i64' else 0;upper=(1<<63)-1 if target=='i64' else MASK
 if exp==2047:return 0 if fraction else ((lower if negative else upper)&MASK)
 magnitude=fraction|((1<<52) if exp else 0);power=exp-1023-52 if exp else -1074
 integer=rounded(magnitude,-power,mode,negative);integer=-integer if negative else integer
 return min(max(integer,lower),upper)&MASK

def equivalent_for(op,observed,expected):
 if op.startswith('to_f32_'):
  if observed>>32:return False
  if expected&0x7f800000==0x7f800000 and expected&0x7fffff:
   return observed&0x7f800000==0x7f800000 and bool(observed&(1<<22))
 return observed==expected

def packed(values):return struct.pack('<'+'Q'*len(values),*values)
