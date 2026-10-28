#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify bounded on-disk dispatcher path; never open an IOKit connection."""
import argparse,hashlib,json,re,struct,subprocess
from pathlib import Path
from compare_video_profile import file_bytes,symbols_and_external_relocations
KERNEL_SHA='7004ebc1020a5c7e3f075c631507f31fdc0ce3fe02e9f01f42dce1d178770a08'
KERNEL_UUID='1291D44A-C0CD-3AC7-A9E4-CA2749B33959'
GE_SHA='44f131a958d48afd6ab675a851330c37506557c9d499484170c886c3731bdbb3'
IO_SHA='37e563d6cf3626101f30b1727a4f60dec02152dff9c74c0269c30c213a7320c8'
DWARF_SHA='2097eb4b103118131b1521d354379e96578f3329655dd2b3bf9aec653ce3cd95'
REGIONS={
 'callExternalMethod':{'offset':0x8231f0,'size':208,'vm':0xffffff8000a231f0,'sha':'c036cdf9149e08ebd9d12246b6a0e513d883bcdd996e3c4e290424c0e0eb5585','elf_sha':'b8955bb7d27110946b0e6c45d4cb115748ff2f3413c48d9d8c25c9bec4398baf'},
 'externalMethod':{'offset':0x818640,'size':1008,'vm':0xffffff8000a18640,'sha':'7aeb288b1e769531cf3f761de1288b8de866fc4f194f8632a3494a0680c85a7a','elf_sha':'95e075ed15fe8d34c093606d8009873ed9bbd69fcd44e620f7ca5533cb383077'},
}
def need(x,m):
 if not x:raise ValueError(m)
def sha(data):return hashlib.sha256(data).hexdigest()
def pinned(path,digest):
 b=Path(path).read_bytes();need(sha(b)==digest,'input hash changed');return b
def elf_text(blob):
 need(len(blob)>=64 and blob[:6]==b'\x7fELF\x02\x01','ELF64 little endian')
 need(struct.unpack_from('<H',blob,16)[0]==1 and struct.unpack_from('<H',blob,56)[0]==0,'non-loadable ET_REL only')
 shoff=struct.unpack_from('<Q',blob,40)[0];entsz,count,strings=struct.unpack_from('<HHH',blob,58)
 need(entsz==64 and 0<count<=128 and strings<count and shoff+entsz*count<=len(blob),'section bounds')
 def hdr(n):return struct.unpack_from('<IIQQQQIIQQ',blob,shoff+64*n)
 sh=hdr(strings);need(sh[4]+sh[5]<=len(blob),'string bounds');names=blob[sh[4]:sh[4]+sh[5]];found=[]
 for i in range(count):
  h=hdr(i);idx=h[0];need(idx<len(names),'section name offset');end=names.find(b'\0',idx);need(end>=0,'section name terminator')
  if names[idx:end]==b'.text':need(h[4]+h[5]<=len(blob),'text bounds');found.append((h[3],blob[h[4]:h[4]+h[5]]))
 need(len(found)==1,'unique text section');return found[0]
def read_region(root,kernel,name):
 pin=REGIONS[name];folder=root/('region-'+name);blob=pinned(folder/'analysis.private.elf',pin['elf_sha']);vm,section=elf_text(blob)
 need(vm==pin['vm'] and len(section)==pin['size'] and sha(section)==pin['sha'],'ELF section identity')
 need(kernel[pin['offset']:pin['offset']+pin['size']]==section,'ELF and on-disk kernel differ')
 return folder/'analysis.private.elf'
def instructions(path,extra=()):
 cmd=['xcrun','llvm-objdump','-d','--x86-asm-syntax=intel',*extra,str(path)];p=subprocess.run(cmd,capture_output=True,text=True,check=True,timeout=30);rows={}
 for line in p.stdout.splitlines():
  m=re.match(r'^\s*([0-9a-fA-F]+):\s+(?:(?:[0-9a-fA-F]{2})\s+)+(.+)$',line)
  if m:rows[int(m.group(1),16)]=re.sub(r'\s+',' ',m.group(2).split('##')[0].split('#')[0].strip())
 return rows
def check_rows(rows,expected):
 for addr,pattern in expected.items():need(addr in rows and re.search(pattern,rows[addr]),'instruction mismatch '+hex(addr))
def relocation(relocs,address,name):
 found=relocs.get(address,[]);need(len(found)==1,'relocation count');r=found[0];need(r['symbol']['name']==name and r['external']==1 and r['length_code']==3 and r['type']==0 and not r['pc_relative'],'relocation target')
def predict(selector,normal_client_branch,ready,sync_slot_zero,no_memory_descriptors):
 """Conditional static inference; caller supplies assumptions, not observations."""
 vals=(normal_client_branch,ready,sync_slot_zero,no_memory_descriptors)
 if type(selector) is not int or not 0<=selector<=0xffffffff or any(type(v) is not bool for v in vals):return 'REFUSED_INVALID_INPUT'
 if not normal_client_branch:return 'UNKNOWN_OTHER_CLIENT_BRANCH'
 if not ready:return 'CONDITIONAL_NOT_READY'
 if selector==6:return 'UNKNOWN_SPECIAL_DISPATCH'
 if not sync_slot_zero:return 'UNKNOWN_ASYNCHRONOUS'
 if not no_memory_descriptors:return 'UNKNOWN_DESCRIPTOR_PATH'
 if selector>7:return 'CONDITIONAL_UNSUPPORTED'
 return 'UNKNOWN_SUPPORTED_INDEX'
def audit(a):
 kernel=pinned(a.kernel,KERNEL_SHA);ge=pinned(a.ge,GE_SHA);io=pinned(a.io,IO_SHA);uuid=subprocess.check_output(['sysctl','-n','kern.uuid'],text=True).strip();need(uuid==KERNEL_UUID,'running kernel UUID changed');dwarf=pinned(a.lab/'IOExternalMethodArguments.dwarf.private.txt',DWARF_SHA).decode()
 for name,offset in [('asyncWakePort','08'),('structureInputDescriptor','40'),('structureOutputDescriptor','68')]:
  pattern=r'DW_AT_name\s*\("'+name+r'"\)(?:(?!DW_TAG_member).)*DW_AT_data_member_location\s*\(0x'+offset+r'\)'
  need(re.search(pattern,dwarf,re.S),'DWARF field '+name)
 k1=read_region(a.lab,kernel,'callExternalMethod');k2=read_region(a.lab,kernel,'externalMethod')
 _,gr=symbols_and_external_relocations(ge);_,ir=symbols_and_external_relocations(io)
 relocation(gr,0x91848,'__ZN15IOAccelContext214externalMethodEjP25IOExternalMethodArgumentsP24IOExternalMethodDispatchP8OSObjectPv')
 relocation(gr,0x91938,'__ZN15IOAccelContext226getTargetAndMethodForIndexEPP9IOServicej')
 relocation(ir,0x73250,'__ZN12IOUserClient14externalMethodEjP25IOExternalMethodArgumentsP24IOExternalMethodDispatchP8OSObjectPv')
 for st,n,h in [(0x8656,52,'1f72c9f8b91d9fc78690faddaf1ffd76c79cdf4f7e9b7bc4dd7eaabe88888d5f'),(0x860a,76,'aee1728e8f66dc533ec275c689f4da0a5946787357ab0565ae7c7863f8562b6b')]:
  _,raw=file_bytes(io,st,n);need(sha(raw)==h,'IOAccel function hash')
 rows=instructions(k1);check_rows(rows,{0xffffff8000a2325c:r'test byte ptr \[rbx \+ 0x9b\], 0x2',0xffffff8000a23269:r'jne 0xffffff8000a2327b',0xffffff8000a2326b:r'xor ecx, ecx',0xffffff8000a2326d:r'xor r8d, r8d',0xffffff8000a23270:r'xor r9d, r9d',0xffffff8000a23273:r'call qword ptr \[rax \+ 0x850\]'})
 rows=instructions(k2);check_rows(rows,{0xffffff8000a18651:r'test rcx, rcx',0xffffff8000a18654:r'je 0xffffff8000a186b0',0xffffff8000a186b7:r'cmp qword ptr \[rdx \+ 0x40\], 0x0',0xffffff8000a186c2:r'cmp qword ptr \[rdx \+ 0x68\], 0x0',0xffffff8000a186db:r'cmp qword ptr \[rdx \+ 0x8\], 0x0',0xffffff8000a186f1:r'je 0xffffff8000a18848',0xffffff8000a18848:r'call qword ptr \[rcx \+ 0x940\]',0xffffff8000a1884e:r'test rax, rax',0xffffff8000a18860:r'mov esi, 0xe00002c7',0xffffff8000a18868:r'jne 0xffffff8000a189ed',0xffffff8000a189ed:r'mov eax, esi'})
 rows=instructions(a.io,['--start-address=0x860a','--stop-address=0x868a']);check_rows(rows,{0x862d:r'cmp edx, 0x7',0x8630:r'ja 0x8648',0x8648:r'xor eax, eax',0x865a:r'test byte ptr \[rdi \+ 0x698\], 0x1',0x8661:r'je 0x8683',0x8663:r'cmp esi, 0x6',0x866d:r'cmove rcx, rax',0x867d:r'jmp qword ptr \[rax \+ 0x860\]',0x8683:r'mov eax, 0xe00002d8'})
 return {'status':'STATIC_CONDITIONAL_SYNC_PATH_PASS','kernel_SHA256':KERNEL_SHA,'ge_SHA256':GE_SHA,'io_SHA256':IO_SHA,'dwarf_capture_SHA256':DWARF_SHA,'kernel_UUID_observed':uuid,'kernel_memory_read':False,'conditions':['on-disk vtable relocations represent the actual initialized object and targets','callExternalMethod chooses the normal branch (client flag 0x2 clear)','context ready bit set','dispatch pointer null, selector not 6','the 64-bit word at arguments +0x08 is zero and input/output memory descriptors are null','selector above 7'],'conditional_result':'kIOReturnUnsupported 0xe00002c7','selector_0x105_model':predict(0x105,True,True,True,True),'other_selector_or_dispatch_paths':'unknown','observed_live_selector':False,'video_decode_proved':False,'notes':['Kernel UUID equality is not a live kernel byte comparison.','Target connection, context state, flags, dispatch and descriptor values are not observed by this audit.','No selector was called or GPU video work executed.']}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel',type=Path,required=True);p.add_argument('--ge',type=Path,required=True);p.add_argument('--io',type=Path,required=True);p.add_argument('--lab',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args();need(not a.out.exists() and a.out.parent.is_dir(),'fresh output');x=audit(a)
 with a.out.open('x') as f:json.dump(x,f,indent=2,sort_keys=True);f.write('\n')
 print(json.dumps(x,sort_keys=True))
if __name__=='__main__':main()
