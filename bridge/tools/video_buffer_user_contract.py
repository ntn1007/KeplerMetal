#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify bounded user-mode IOAccelerator cache evidence; no function is invoked."""
import argparse,hashlib,json,re,struct,subprocess,sys
from pathlib import Path
from inspect_video_cache import Cache,inspect,image_map,linkedit_read,cstring,stub_symbol

IMAGE='/System/Library/PrivateFrameworks/IOAccelerator.framework/Versions/A/IOAccelerator'
UUID='198a776afe0335ee8e537b9f14caabaa'
# Frozen function bytes are retained only in the local lab; hashes and symbols here.
FUNCTIONS=[
 ('buffer','function-00','_IOAccelVideoContextRequestDataBuffer','de75f21e9d308e0128792a8d867872d53ae3e79ef787dc08ac8b50be161faabf',0x7ff80f8928bd),
 ('buffer','function-01','_IOAccelContextRequestDataBuffer','35d66134005b9fcfb387423a3ef975bc6cec4b62aeb7c8b82a46e2cfc284cb29',0x7ff80f890b36),
 ('buffer','function-04','_IOAccelResourceCreateDataBuffer','4a2716ebd724b52e4c2cab4e345094eab8a0bbb24a5316ee565478d6732f8059',0x7ff80f88ec14),
 ('lifecycle','function-00','_IOAccelVideoContextCreate','8e3f084ec62d063d193bcead7fb4271012ff3334c909d1e0eba90465385e6fc6',0x7ff80f8902b0),
 ('lifecycle','function-01','_IOAccelContextCreate','46435a813d343f15205827de6fcc73c914701d6571c39b23431eb970b27c0e84',0x7ff80f88e554),
 ('lifecycle','function-02','_IOAccelDeviceCreate','b337296aceb0aed820f6965ba3815ee550e5b91a16990f0fa370fd081f2da648',0x7ff80f89021a),
 ('lifecycle','function-03','_IOAccelSharedCreate','42cb0f1632b36c0b56a8de0fe60e1f744b8407270f309a23a6f2f30d3a33904d',0x7ff80f88e431),
 ('lifecycle','function-04','_IOAccelVideoContextGetDataBufferClassCount','f40c391d17accafbfed049d584d836c59d2e810da7f940573f621b247c6f8eca',0x7ff80f890301),
 ('device','function-00','_IOAccelContextGetDataBufferClassCount','4b4717fecd4470eb59b449335296cc011e4ad1edebf818b535992266fdd0e23d',0x7ff80f88ed71),
 ('device','function-02','_IOAccelDeviceCreateWithAPIProperty','392ef70adb9a4175266bb9b29611428f4cb00ab1a8a518ce59e950ffa915294a',0x7ff80f88df60)]

def digest(b):return hashlib.sha256(b).hexdigest()
def branch(data,start,site,opcode):
    pos=site-start
    if pos<0 or pos+5>len(data) or data[pos]!=opcode:raise ValueError('Expected bounded direct branch missing')
    return site+5+struct.unpack_from('<i',data,pos+1)[0]

def symbols(cache,img,wanted):
    t=img['symbol_table'];raw=linkedit_read(cache,img,t['file_offset'],t['count']*16);result={}
    for k in range(t['count']):
        off,kind,_,_,addr=struct.unpack_from('<IBBHQ',raw,16*k)
        if not off or off>=t['strings_size'] or kind&14!=14:continue
        s=linkedit_read(cache,img,t['strings_offset']+off,min(4096,t['strings_size']-off));name=cstring(s,0,len(s))
        if name in wanted:
            if name in result:raise ValueError('Ambiguous cache symbol: '+name)
            result[name]=addr
    if set(result)!=wanted:raise ValueError('Missing cache symbol')
    return result

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('cache','buffer','lifecycle','device','out'):p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();out=a.out.resolve()
    if out.exists() or not out.parent.is_dir():raise ValueError('Fresh output directory required')
    cache=Cache(a.cache.resolve());mappings=image_map(a.cache.with_name(a.cache.name+'.map'),IMAGE)
    img,starts=inspect(cache,mappings[0]['start'],IMAGE)
    if img['UUID']!=UUID:raise ValueError('Cache image UUID differs')
    addresses=symbols(cache,img,{f[2] for f in FUNCTIONS});out.mkdir();rows=[];data_by_name={};text_by_name={}
    part_hashes={}
    for group in ('buffer','lifecycle','device'):
        capture=json.loads((getattr(a,group)/'capture.json').read_text())
        if capture['status']!='PASS' or capture['image_UUID']!=UUID:raise ValueError('Capture image identity differs')
        for part in capture['cache_parts_read']:
            part_path=a.cache.parent/part['name']
            if part_path.resolve()!=Path(part['path']).resolve():raise ValueError('Cache part path differs')
            if part['name'] not in part_hashes:
                h=hashlib.sha256()
                with part_path.open('rb') as f:
                    for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
                part_hashes[part['name']]=h.hexdigest()
            if part_hashes[part['name']]!=part['SHA256']:raise ValueError('Cache part SHA differs')
    for group,folder,name,expected,start in FUNCTIONS:
        if addresses[name]!=start or start not in starts:raise ValueError('Symbol or function boundary differs')
        src=getattr(a,group)/folder;meta=json.loads((src/'metadata.json').read_text());region=meta['region'];data=(src/'function-region.private.bin').read_bytes()
        if (meta['image']['UUID']!=UUID or meta['status']!='PASS' or not meta['region_captured_privately'] or region['name']!=name or
            region['boundary_source']!='LC_FUNCTION_STARTS' or region['start_VM']!=start or region['end_VM']!=start+len(data) or
            region['bytes']!=len(data) or region['SHA256']!=expected or digest(data)!=expected or digest(cache.read(start,len(data)))!=expected):
            raise ValueError('Captured function differs from pinned live cache: '+name)
        dest=out/folder;dest=out/(group+'-'+folder);dest.mkdir()
        obj=dest/'analysis.private.o'
        subprocess.run([sys.executable,str(Path(__file__).with_name('video_region_analysis_object.py')),'--metadata',str(src/'metadata.json'),'--out',str(obj)],check=True,capture_output=True,timeout=30)
        d=subprocess.run(['xcrun','llvm-objdump','-d','--x86-asm-syntax=intel',str(obj)],check=True,capture_output=True,text=True,timeout=30).stdout
        (dest/'disassembly.private.txt').write_text(d);data_by_name[name]=(start,data);text_by_name[name]=d
        rows.append({'symbol':name,'start_VM':hex(start),'region_SHA256':expected,'bytes':len(data),'metadata_SHA256':digest((src/'metadata.json').read_bytes()),'disassembly_SHA256':digest(d.encode())})
    def check(name,needles):
        text=text_by_name[name]
        if not all(re.search(x,text) for x in needles):raise ValueError('Disassembly anchor differs: '+name)
    def edge(name,site,opcode,target):
        start,data=data_by_name[name]
        if branch(data,start,site,opcode)!=target:raise ValueError('Direct call or tail target differs: '+name)
    def imported(name,site,target,symbol):
        edge(name,site,0xe8,target);binding=stub_symbol(cache,img,target)
        if not binding or binding.get('static_symbol')!=symbol:raise ValueError('Static import binding differs: '+symbol)
    edge('_IOAccelVideoContextRequestDataBuffer',0x7ff80f8928c2,0xe9,addresses['_IOAccelContextRequestDataBuffer'])
    edge('_IOAccelVideoContextCreate',0x7ff80f8902ba,0xe9,addresses['_IOAccelContextCreate'])
    edge('_IOAccelDeviceCreate',0x7ff80f890221,0xe9,addresses['_IOAccelDeviceCreateWithAPIProperty'])
    edge('_IOAccelVideoContextGetDataBufferClassCount',0x7ff80f890306,0xe9,addresses['_IOAccelContextGetDataBufferClassCount'])
    edge('_IOAccelContextRequestDataBuffer',0x7ff80f890bd9,0xe8,addresses['_IOAccelResourceCreateDataBuffer'])
    for n,site,stub,sym in [('_IOAccelContextRequestDataBuffer',0x7ff80f890baf,0x7ff80f89476a,'_IOConnectCallStructMethod'),
      ('_IOAccelContextCreate',0x7ff80f88e57c,0x7ff80f8947a6,'_IOServiceOpen'),
      ('_IOAccelContextCreate',0x7ff80f88e69d,0x7ff80f89474c,'_IOConnectAddClient'),
      ('_IOAccelSharedCreate',0x7ff80f88e458,0x7ff80f8947a6,'_IOServiceOpen'),
      ('_IOAccelSharedCreate',0x7ff80f88e4d8,0x7ff80f89476a,'_IOConnectCallStructMethod'),
      ('_IOAccelDeviceCreateWithAPIProperty',0x7ff80f88df9b,0x7ff80f8947a6,'_IOServiceOpen'),
      ('_IOAccelDeviceCreateWithAPIProperty',0x7ff80f88e06f,0x7ff80f89476a,'_IOConnectCallStructMethod')]:imported(n,site,stub,sym)
    check('_IOAccelContextRequestDataBuffer',[r'cmp\s+esi, 0xf',r'mov\s+dword ptr \[r12\], esi',r'mov\s+dword ptr \[r12 \+ 0x4\], edx',r'mov\s+ecx, 0x8',r'mov\s+esi, 0x3',r'mov\s+eax, dword ptr \[rax \+ 0x3c\]',r'lea\s+r13, \[rax \+ 0x30\]'])
    check('_IOAccelVideoContextCreate',[r'mov\s+esi, 0x3'])
    check('_IOAccelContextCreate',[r'mov\s+qword ptr \[rax \+ 0x10\], rbx',r'mov\s+dword ptr \[r14 \+ 0xa4\], 0x10'])
    check('_IOAccelContextGetDataBufferClassCount',[r'mov\s+eax, dword ptr \[rdi \+ 0xa4\]'])
    check('_IOAccelSharedCreate',[r'mov\s+qword ptr \[rax \+ 0x10\], r15',r'mov\s+edx, 0x6',r'mov\s+esi, 0x9',r'mov\s+qword ptr \[r9\], 0x10'])
    check('_IOAccelDeviceCreateWithAPIProperty',[r'mov\s+edx, 0x5',r'mov\s+esi, 0x2',r'mov\s+qword ptr \[r9\], 0x258',r'mov\s+eax, dword ptr \[rbp - 0x270\]',r'mov\s+dword ptr \[rbx \+ 0x3c\], eax'])
    result={'status':'PASS','image':IMAGE,'image_UUID':UUID,'functions':rows,'type3_context_create_static':True,
      'request_selector':3,'request_input_bytes':8,'request_first_two_u32_from_registers':['esi','edx'],
      'user_context_slot_count':16,'buffer_output_size':'48 + device response-2 u32 at offset 16',
      'cache_part_SHA256':part_hashes,'kernel_class_count_runtime_observed':False,
      'shared_constructor_open_type':6,'shared_constructor_selector':9,'device_constructor_open_type':5,
      'device_constructor_selector':2,'runtime_bindings_observed':False,'private_function_invocations':0,'GPU_commands':0,
      'qualification':'Static x86_64 cache evidence only; private API prototype, resource lifetimes and valid input values remain unqualified.'}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':'PASS','functions':len(rows),'private_function_invocations':0,'GPU_commands':0}))

if __name__=='__main__':main()
