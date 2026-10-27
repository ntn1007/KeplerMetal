#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify static user-mode CF lifecycle evidence without invoking driver code."""
import argparse,hashlib,json,re,struct,subprocess,sys
from pathlib import Path
from inspect_video_cache import Cache,inspect,image_map,stub_symbol
from video_buffer_user_contract import IMAGE,UUID,branch,digest

CACHE_SHA='01d2fb67994fe5f4a6846263144432af24a1a450993f917e54de53351e6708be'
REG={
 'device':('function-00',0x7ff80f88e20d,0x7ff84119c338,0x7ff80f890d9a,'cff3c4bbab19b2ad4e1cc61eb84d41ac200e8dba9ef1dc61e083aabd57cf16c7','3ac14db31487f70610f9dadfbbf56dbe50fd822507bee6b94f6ec4fed41b590b'),
 'shared':('function-01',0x7ff80f88e52c,0x7ff84119c418,0x7ff80f89076c,'dbdb82022553235ebf31f9668d76904cf5e5bfa789d973c717eae6f09d6822cc','8376616df43e4aafc1cd09131887312cc0605b95be5ef0497c49e5d078502be6'),
 'context':('function-02',0x7ff80f88e6d0,0x7ff84119c4d8,0x7ff80f890906,'c46af5c0c46a561a02c61dafa89f1567fbd0d31b36667bd9d35f05c53b442ec2','7eee3cf95ce9e8016084c1ecedbb87f53fe8c565939ac774c6851eaf1ea13e87'),
 'resource':('function-03',0x7ff80f88ed4e,0x7ff84119c638,0x7ff80f88f6a5,'f52842657ee142fffcc51dba302a83200c86811906056ff2a348022db883f333','17f9d42efe9b91891078eebb6dbe32fd90fd00fcf542079507ec5ba3d4cde3f7')}
EXTRA={
 'resource_alloc':('resource_alloc','function-00',0x7ff80f88ecc9,'ac30d8ae45293a22c31db0b54401d88381dbbcf6bf9dd8fa17294315c29d0abf'),
 'resource_getter':('getters','function-03',0x7ff80f88ed87,'e044de81e27880d3ad728f770517a2badaa9188d4afdb5fc7723ee86e044e0c6'),
 'video_getter':('getters','function-02',0x7ff80f89030b,'323f4e620cca32a89c2f07fe7ed27f180103591f778fcc66b178729dc50ed30b')}

def file_sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for x in iter(lambda:f.read(1024*1024),b''):h.update(x)
    return h.hexdigest()

def rip_lea(data,start,site):
    off=site-start
    if off<0 or off+7>len(data) or data[off:off+3]!=b'\x48\x8d\x3d':raise ValueError('Expected RIP-relative LEA missing')
    return site+7+struct.unpack_from('<i',data,off+3)[0]

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for n in ('cache','registration','resource-alloc','getters','device','shared','context','resource','out'):
        p.add_argument('--'+n,type=Path,required=True)
    a=p.parse_args();out=a.out.resolve();cache_path=a.cache.resolve()
    if out.exists() or not out.parent.is_dir():raise ValueError('Fresh output directory required')
    if file_sha(cache_path)!=CACHE_SHA:raise ValueError('Exact cache SHA differs')
    c=Cache(cache_path);img,starts=inspect(c,image_map(cache_path.with_name(cache_path.name+'.map'),IMAGE)[0]['start'],IMAGE)
    if img['UUID']!=UUID:raise ValueError('Image UUID differs')
    out.mkdir();records=[];data={};dis={}
    def load(label,src,start,expected):
        m=json.loads((src/'metadata.json').read_text());r=m['region'];b=(src/'function-region.private.bin').read_bytes()
        if (m['image']['UUID']!=UUID or m['status']!='PASS' or not m['region_captured_privately'] or
            r['boundary_source']!='LC_FUNCTION_STARTS' or r['start_VM']!=start or r['target_VM']!=start or
            r['end_VM']!=start+len(b) or r['bytes']!=len(b) or r['SHA256']!=expected or digest(b)!=expected or
            start not in starts or digest(c.read(start,len(b)))!=expected):raise ValueError('Captured region mismatch: '+label)
        d=out/label;d.mkdir();obj=d/'analysis.private.o'
        subprocess.run([sys.executable,str(Path(__file__).with_name('video_region_analysis_object.py')),'--metadata',str(src/'metadata.json'),'--out',str(obj)],check=True,capture_output=True,timeout=30)
        text=subprocess.run(['xcrun','llvm-objdump','-d','--x86-asm-syntax=intel',str(obj)],check=True,capture_output=True,text=True,timeout=30).stdout
        (d/'disassembly.private.txt').write_text(text);data[label]=(start,b);dis[label]=text
        records.append({'label':label,'start_VM':hex(start),'region_SHA256':expected,'bytes':len(b),'metadata_SHA256':digest((src/'metadata.json').read_bytes())})
    for key,(folder,reg_start,class_addr,finalizer,reg_sha,final_sha) in REG.items():
        load(key+'_registration',a.registration/folder,reg_start,reg_sha);load(key+'_finalizer',getattr(a,key),finalizer,final_sha)
        start,b=data[key+'_registration'];site=start+4
        if rip_lea(b,start,site)!=class_addr or branch(b,start,start+11,0xe8)!=0x7ff80f8947e2:
            raise ValueError('Class registration path differs')
        reg_stub=stub_symbol(c,img,0x7ff80f8947e2)
        if not reg_stub or reg_stub.get('static_symbol')!='__CFRuntimeRegisterClass':raise ValueError('Class registration import differs')
        if struct.unpack('<Q',c.read(class_addr,8))[0]!=0 or c.pointer_v2(class_addr+0x20)!=finalizer:
            raise ValueError('Class version/finalizer pointer differs')
        nameptr=c.pointer_v2(class_addr+8);actual=c.read(nameptr,64).split(b'\0',1)[0].decode('ascii')
        if actual!='IOAccel'+key.capitalize():raise ValueError('Class name differs')
    for label,(arg,folder,start,h) in EXTRA.items():load(label,getattr(a,arg)/folder,start,h)
    def call(label,site,target,symbol):
        start,b=data[label]
        if branch(b,start,site,0xe8)!=target:raise ValueError('Call target differs: '+label)
        entry=stub_symbol(c,img,target)
        if not entry or entry.get('static_symbol')!=symbol:raise ValueError('Static binding differs: '+symbol)
    call('context_finalizer',0x7ff80f890939,0x7ff80f894710,'_CFRelease')
    call('context_finalizer',0x7ff80f890953,0x7ff80f894776,'_IOConnectRelease')
    call('shared_finalizer',0x7ff80f890791,0x7ff80f894776,'_IOConnectRelease')
    call('device_finalizer',0x7ff80f890dc3,0x7ff80f894776,'_IOConnectRelease')
    call('resource_alloc',0x7ff80f88ed10,0x7ff80f894716,'_CFRetain')
    call('resource_finalizer',0x7ff80f88f764,0x7ff80f894710,'_CFRelease')
    call('resource_finalizer',0x7ff80f88f745,0x7ff80f89475e,'_IOConnectCallMethod')
    start,b=data['video_getter']
    if branch(b,start,0x7ff80f890310,0xe9)!=0x7ff80f88ed87:raise ValueError('Video getter target differs')
    anchors={'context_finalizer':[r'mov\s+rdi, qword ptr \[rbx \+ 8\*r14 \+ 0x20\]',r'cmp\s+r14, 0x10'],
      'resource_alloc':[r'mov\s+rdi, rbx',r'mov\s+qword ptr \[r14 \+ 0x18\], rbx'],
      'resource_finalizer':[r'dec\s+dword ptr \[rax \+ 0x18\]',r'mov\s+esi, 0x1',r'mov\s+edi, dword ptr \[rax \+ 0x18\]'],
      'resource_getter':[r'mov\s+rax, qword ptr \[rdi \+ 8\*rax \+ 0x20\]']}
    for label,patterns in anchors.items():
        if not all(re.search(pattern,dis[label]) for pattern in patterns):raise ValueError('Instruction observation differs: '+label)
    before_return=dis['resource_getter'].split('\tret',1)[0]
    if re.search(r'\bcall\s',before_return):raise ValueError('Unexpected resource getter call')
    result={'status':'PASS','cache_SHA256':CACHE_SHA,'image_UUID':UUID,'records':records,
      'class_layout_reference':'https://github.com/apple-oss-distributions/CF/blob/dc54c6bb1c1e5e0b9486c1d26dd5bef110b20bf3/CFRuntime.h',
      'class_finalize_offset':32,'context_release_before_connection_release':True,
      'resource_constructor_retains_shared':True,'resource_finalizer_releases_shared':True,
      'context_getter_direct_retain_observed':False,'resource_finalizer_conditional_shared_selector':1,
      'runtime_callback_dispatch_observed':False,'valid_resource_values_qualified':False,'private_function_invocations':0,'GPU_commands':0}
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':'PASS','functions':len(records),'runtime_callback_dispatch_observed':False,'GPU_commands':0}))

if __name__=='__main__':main()
