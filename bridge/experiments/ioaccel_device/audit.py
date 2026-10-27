#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify two private captures and bounded x86 disassembly, without calling GPU APIs."""
import argparse,hashlib,json,re,subprocess,tempfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
EXPECTED='1f97e27b78826a4c4801f851173d67e97d00f7b1668fe5882e19895eb74b9ece'
def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,msg):
 if not ok:raise ValueError(msg)
def check_code(b,digest):require(len(b)==256 and sha(b)==digest==EXPECTED,'Configuration entry mismatch')
def disassemble(path,work):
 require(not any(c in str(path) for c in ('"','\n','\r')),'Unsupported input path')
 with tempfile.TemporaryDirectory(prefix='device-analysis-',dir=work) as t:
  t=Path(t);asm=t/'wrapper.s';obj=t/'private.o';asm.write_text('.text\n.globl _entry\n_entry:\n.incbin "'+str(path)+'"\n')
  subprocess.run(['xcrun','clang','-arch','x86_64','-c',str(asm),'-o',str(obj)],capture_output=True,check=True,timeout=30)
  text=subprocess.run(['xcrun','llvm-objdump','-d','--no-show-raw-insn',str(obj)],capture_output=True,text=True,check=True,timeout=30).stdout
 rows={}
 for line in text.splitlines():
  m=re.match(r'^\s*([0-9a-f]+):\s*(.*?)\s*$',line)
  if m:
   offset=int(m.group(1),16);require(offset not in rows,'Duplicate disassembly offset');rows[offset]=re.sub(r'\s+',' ',m.group(2).split('##')[0].strip())
 checks={0x11:r'^movl \$0xe00002c2, %ebx',0x16:r'^testq %rdi, %rdi$',0x19:r'^je 0x79',0x1b:r'^movq %rcx, %r12$',0x1e:r'^movq %rdx, %r13$',0x21:r'^movq %rsi, %r14$',0x24:r'^movq %rdi, %r15$',0x27:r'^movq %r8, -0x30\(%rbp\)$',0x2b:r'^movq %r9, -0x38\(%rbp\)$',0x2f:r'^callq ',0x34:r'^cmpq ',0x3b:r'^jne 0x79',0x3d:r'^movl 0x270\(%r15\), %eax$',0x44:r'^movl %eax, \(%r14\)$',0x47:r'^movl 0x274\(%r15\), %eax$',0x4e:r'^movl %eax, \(%r13\)$',0x52:r'^movl 0x278\(%r15\), %eax$',0x59:r'^movl %eax, \(%r12\)$',0x5d:r'^movl 0x280\(%r15\), %eax$',0x64:r'^movq -0x30\(%rbp\), %rcx$',0x68:r'^movl %eax, \(%rcx\)$',0x6a:r'^movl 0x288\(%r15\), %eax$',0x71:r'^movq -0x38\(%rbp\), %rcx$',0x75:r'^movl %eax, \(%rcx\)$',0x77:r'^xorl %ebx, %ebx$',0x79:r'^movl %ebx, %eax$',0x89:r'^retq$'}
 for address,pattern in checks.items():require(address in rows and re.search(pattern,rows[address]),'Instruction mismatch '+hex(address))
 require(all(address in rows for address in checks),'Incomplete disassembly');return len(checks)
def audit(paths,work):
 require(len(paths)==2 and len(set(paths))==2 and work.is_dir(),'Two distinct captures and work directory required')
 records=[];codes=[];current=sha((HERE/'capture.py').read_bytes())
 for root in paths:
  d=json.loads((root/'metadata.json').read_text());require(d['status']=='PASS' and d['image_UUID']=='198a776afe0335ee8e537b9f14caabaa' and d['capture_source_SHA256']==current,'Capture identity changed')
  require(not d['function_calls_made'] and not d['gpu_commands_submitted'] and not d['code_bytes_distributed'],'Capture scope changed')
  require(d['type_query']['resolved_symbol']=='CFGetTypeID' and d['type_query']['exact_symbol'] and not d['type_query']['function_called'],'Resolved type-query target changed')
  rows={x['name']:x for x in d['functions']};require(set(rows)=={'IOAccelDeviceGetConfig','IOAccelDeviceCreate','IOAccelDeviceRelease'} and len(d['functions'])==3,'Function set changed')
  for name,row in rows.items():
   b=(root/(name+'.private.bin')).read_bytes();require(len(b)==row['bytes']==256 and sha(b)==row['entry_sha256'],'Entry differs: '+name)
  code=(root/'IOAccelDeviceGetConfig.private.bin').read_bytes();check_code(code,rows['IOAccelDeviceGetConfig']['entry_sha256']);records.append(d);codes.append(code)
 require(records[0]==records[1] and codes[0]==codes[1],'Captures differ')
 n=disassemble(paths[0]/'IOAccelDeviceGetConfig.private.bin',work)
 altered=bytes([codes[0][0]^1])+codes[0][1:]
 try:check_code(altered,EXPECTED)
 except ValueError:negative='EXPECTED_REFUSAL'
 else:raise ValueError('Altered entry accepted')
 return {'status':'PASS','capture_count':2,'IOAccelerator_UUID':records[0]['image_UUID'],'configuration_entry_SHA256':EXPECTED,'type_query_resolved':'CFGetTypeID','bounded_instruction_checks':n,'object_field_offsets':['0x270','0x274','0x278','0x280','0x288'],'output_width_bits':32,'output_word_count':5,'null_object_refusal_observed_statically':True,'type_test_observed_statically':True,'output_values_or_semantics_proved':False,'actual_device_or_function_called':False,'gpu_execution_proved':False,'corrupted_entry_control':negative,'limitations':['Function bytes and current binding are observed in isolated capture processes; the selected function itself was not invoked.','The compared expected type identifier and field semantics remain unknown.','The adjacent entry bytes exceed the verified function boundary; only offsets through the first return were interpreted.']}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--captures',nargs=2,type=Path,required=True);p.add_argument('--work',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();require(not a.out.exists() and a.out.parent.is_dir(),'Fresh report required');r=audit([x.resolve() for x in a.captures],a.work.resolve())
 with a.out.open('x') as f:json.dump(r,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(r))
if __name__=='__main__':main()
