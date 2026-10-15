#!/usr/bin/env python3
"""Conservative x86_64 layout of selected captured Objective-C type encodings.
Not a general C++ ABI parser: bitfields, unknown by-value types and malformed
encodings are rejected. Pointer pointees are skipped, never dereferenced.
"""
class Encoding:
 def __init__(self,text):
  if len(text)>262144:raise ValueError('Encoding too long')
  self.text=text;self.i=0
 def quote(self):
  assert self.text[self.i]=='"';self.i+=1;start=self.i
  while self.i<len(self.text) and self.text[self.i]!='"':self.i+=1
  if self.i==len(self.text):raise ValueError('Unclosed quote')
  result=self.text[start:self.i];self.i+=1;return result
 def skip_aggregate(self):
  pairs={'{':'}','(':')','[':']'};stack=[pairs[self.text[self.i]]];self.i+=1
  while stack:
   if self.i>=len(self.text):raise ValueError('Unclosed pointee')
   c=self.text[self.i]
   if c=='"':self.quote();continue
   self.i+=1
   if c in pairs:stack.append(pairs[c])
   elif c in pairs.values():
    if c!=stack.pop():raise ValueError('Bad delimiter')
 def skip_type(self):
  while self.i<len(self.text) and self.text[self.i] in 'rnNoORV':self.i+=1
  if self.i>=len(self.text):raise ValueError('Missing type')
  c=self.text[self.i]
  if c=='^':self.i+=1;self.skip_type()
  elif c in '{([':self.skip_aggregate()
  elif c=='@':
   self.i+=1
   if self.i<len(self.text) and self.text[self.i]=='"':self.quote()
   elif self.i<len(self.text) and self.text[self.i]=='?':self.i+=1
  elif c=='b':
   self.i+=1
   while self.i<len(self.text) and self.text[self.i].isdigit():self.i+=1
  else:self.i+=1
 def parse(self,depth=0):
  if depth>96:raise ValueError('Too deep')
  while self.i<len(self.text) and self.text[self.i] in 'rnNoORV':self.i+=1
  start=self.i;c=self.text[self.i];self.i+=1
  primitive={'c':(1,1),'C':(1,1),'B':(1,1),'s':(2,2),'S':(2,2),'i':(4,4),'I':(4,4),'q':(8,8),'Q':(8,8),'f':(4,4),'d':(8,8),'D':(16,16),'v':(0,1),'*':(8,8),'#':(8,8),':':(8,8)}
  fields=[];name=None
  if c in primitive:size,align=primitive[c]
  elif c=='@':
   size,align=8,8
   if self.i<len(self.text) and self.text[self.i]=='"':self.quote()
   elif self.i<len(self.text) and self.text[self.i]=='?':self.i+=1
  elif c=='^':self.skip_type();size,align=8,8
  elif c=='[':
   nstart=self.i
   while self.text[self.i].isdigit():self.i+=1
   count=int(self.text[nstart:self.i]);child=self.parse(depth+1)
   if self.text[self.i]!=']':raise ValueError('Bad array')
   self.i+=1;size,align=count*child['size'],child['alignment']
  elif c in '{(':
   closing='}' if c=='{' else ')';nstart=self.i
   while self.text[self.i] not in '='+closing:self.i+=1
   name=self.text[nstart:self.i]
   if self.text[self.i]==closing:raise ValueError('Opaque by-value aggregate')
   self.i+=1;size,align=0,1
   while self.text[self.i]!=closing:
    label=self.quote() if self.text[self.i]=='"' else None
    field=self.parse(depth+1);align=max(align,field['alignment']);offset=0 if c=='(' else (size+field['alignment']-1)//field['alignment']*field['alignment']
    fields.append({**field,'offset':offset,'label':label});size=max(size,offset+field['size'])
   self.i+=1;size=(size+align-1)//align*align
  else:raise ValueError('Unsupported by-value encoding '+c)
  return {'type':self.text[start:self.i],'name':name,'size':size,'alignment':align,'fields':fields}
def layout(text):
 parser=Encoding(text);result=parser.parse()
 if parser.i!=len(text):raise ValueError('Trailing encoding')
 return result
