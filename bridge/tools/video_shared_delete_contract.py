#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Inspect pinned shared-client selector metadata without dispatching requests."""
import argparse,hashlib,json,struct,subprocess,tempfile,re,sys
from pathlib import Path
from compare_video_profile import file_bytes,symbols_and_external_relocations
from video_method_contract import IO_SHA,GE_SHA,symbol_one,descriptor
from video_resource_ownership import check_evidence
from video_buffer_lifetime import CACHE_SHA,file_sha
from video_buffer_user_contract import IMAGE,UUID,branch
from inspect_video_cache import Cache,inspect,image_map,stub_symbol

TABLE='__ZN24IOAccelSharedUserClient214sSharedMethodsE'
DELETE='__ZN24IOAccelSharedUserClient215delete_resourceEj'
PARENT='__ZTV24IOAccelSharedUserClient2'
LOOKUP='__ZN14IOAccelShared214lookupResourceEjPPv'
NAMESPACE='__ZNK16IOAccelNamespace8lookupIdEjPPv'
PENDING='__ZN13nvAccelerator24DoPendingReleaseIfNeededEP15nvTextureBuffer'
VIRTUAL='__ZTV18nvSharedUserClient'
EXT='__ZN18nvSharedUserClient14externalMethodEjP25IOExternalMethodArgumentsP24IOExternalMethodDispatchP8OSObjectPv'
TARGET='__ZN18nvSharedUserClient26getTargetAndMethodForIndexEPP9IOServicej'

def digest(data):return hashlib.sha256(data).hexdigest()
def static_tables(io_path,ge_path):
    io,ge=Path(io_path).read_bytes(),Path(ge_path).read_bytes()
    if digest(io)!=IO_SHA or digest(ge)!=GE_SHA:raise ValueError('Exact binary profile differs')
    sy,rel=symbols_and_external_relocations(io)
    if symbol_one(sy,TABLE)['value']!=0x77cb0 or symbol_one(sy,DELETE)['value']!=0x2c470:
        raise ValueError('Shared method symbols differ')
    row=descriptor(io,0x77ce0,(DELETE,0x2c470,0,1,0),rel,sy)
    gsy,grel=symbols_and_external_relocations(ge)
    if symbol_one(gsy,VIRTUAL)['value']!=0x8d180:raise ValueError('Shared subclass vtable differs')
    slots=[]
    for slot,name,target in ((0x850,EXT,0x53284),(0x940,TARGET,0x533a6)):
        cell=0x8d190+slot;raw=file_bytes(ge,cell,8)[1]
        if grel.get(cell) or struct.unpack('<Q',raw)[0]!=target or symbol_one(gsy,name)['value']!=target:
            raise ValueError('Shared subclass slot differs: '+hex(slot))
        slots.append({'slot':hex(slot),'symbol':name,'target_on_disk':hex(target)})
    if symbol_one(sy,PARENT)['value']!=0x77210 or symbol_one(sy,NAMESPACE)['value']!=0x3e84 or symbol_one(gsy,PENDING)['value']!=0xf820:
        raise ValueError('Parent or lookup symbols differ')
    for off,target in ((0x860,0x2da22),(0x950,0x2dbec)):
        cell=0x77210+off
        if rel.get(cell) or struct.unpack('<Q',file_bytes(io,cell,8)[1])[0]!=target:
            raise ValueError('Parent vtable slot differs')
    for cell,name,length,kind,pcrel in ((0x7b1c0,PARENT,3,0,0),(0x5330f,LOOKUP,2,2,1)):
        hits=grel.get(cell,[])
        if len(hits)!=1 or hits[0]['symbol']['name']!=name or (hits[0]['external'],hits[0]['length_code'],hits[0]['type'],hits[0]['pc_relative'])!=(1,length,kind,pcrel):
            raise ValueError('External binding differs: '+name)
    return {'IOAccelerator_SHA256':IO_SHA,'GeForce_SHA256':GE_SHA,'selector':1,
            'legacy_method_table':hex(0x77cb0),'selector_entry':row,'nv_shared_vtable_slots':slots,
            'runtime_dispatch_observed':False,'native_calls':0,'GPU_commands':0}

# REA MCP captures are private local evidence; only identities and hashes are emitted.
EVIDENCE={
 '0x53284':('ge','128401a4c6eae933ede1e773c4d889bae4b07050f35270e206d5d0f182c5e340','ev_25c35a13b5665be2b3eb5f3b9cf4c322e1414be1ab5aa9bf318319ba09e7913d',290,
   ['0x5329e: CMP ESI, 0x1','0x53301: MOV RAX, qword ptr [R13 + 0x20]','0x53305: MOV ESI, dword ptr [RAX]',
    '0x5330e: CALL 0x0011c100','0x5331e: MOV RSI, qword ptr [RBP + -0x40]','0x53322: CALL 0x0000f820','0x5336d: CALL qword ptr [RAX + 0x860]']),
 '0xf820':('pending','0e4e8944fb9b80352cfca9e4e47bd8297c356dd970ca2fc2230f7569f7884fcd','ev_51bc12723d20106ed2e841a5f865a1a867e8c230070ee4f95ed1feaddce28b74',124,
   ['0xf826: MOV EAX, dword ptr [RSI + 0x1c8]','0xf82f: JNS 0x0000f895','0xf83c: MOV dword ptr [RSI + 0x1c8], ECX',
    '0xf84e: CALL qword ptr [RAX + 0x178]','0xf861: CALL qword ptr [RAX + 0x28]','0xf879: MOV qword ptr [RCX + 0x8], RDX']),
 '0x533a6':('ge','70b1835c712f43217d8de80ca4f6dc5a5b26450db3d17235346cbbe9a20c5f70','ev_4c96f2956c8b4a9fc70f0f9f915c0c7abad0be07fdfa6e7e059a176bc5302811',65,
   ['0x533aa: CMP qword ptr [RDI + 0x168], 0x0','0x533b4: LEA EAX, [RDX + -0x100]','0x533ba: CMP EAX, 0x4','0x533e1: JMP qword ptr [RAX + 0x950]']),
 '0x52eca':('ge','268640102f22696f66d592e94b2efccc73a23615b2550f640fae5bf7d12d5f63','ev_dee4ecc0bcbddf6b5e11d65c8baafe7fe2814590080127e9fe5dd710cdaad42d',75,
   ['0x52ee4: MOV RCX, qword ptr [RBX + 0xf8]','0x52ef2: MOV qword ptr [RBX + 0x168], RCX']),
 '0x2da22':('io','b9c9bacc6a73bcc012088155de50c8ca4764c38815b5a8de91dc72910d257fad','ev_0e05021a99cecd09ce893a00b085ede9086928ad8767397fa0d152e4a3908264',446,
   ['0x2da39: TEST ESI, ESI','0x2da45: CMP R15D, 0x11','0x2da9e: CALL qword ptr [RAX + 0x860]']),
 '0x2dbec':('io','3351005dc2280f244f0bdd9a5d60019300ac716262ab3404c004c892c2bc363f','ev_e998879ee7445609aa17ed6c4f97cf46dd7ba807e15615a66d6a247a34185315',38,
   ['0x2dbfd: LEA RCX, [0x77cb0]','0x2dc09: CMP EDX, 0x15','0x2dc0c: CMOVC RAX, RCX']),
 '0x2c470':('io','a3e8cef9aea79565f2a6121e2cb3105566988c2a161cba96c05d6ad1a6033d89','ev_418168271cd4a16376227ae0dc0ae2f05694e4dac289d43aca804a04fce3cb63',278,
   ['0x2c4df: MOV RAX, qword ptr [RBX + 0x100]','0x2c4e6: MOV RDI, qword ptr [RAX + 0x20]',
    '0x2c4f0: CALL 0x00003e84','0x2c4f5: MOV R14D, 0xe00002c2','0x2c503: CMP byte ptr [RDI + 0x14], 0xa',
    '0x2c507: JZ 0x0002c519','0x2c513: CALL qword ptr [RAX + 0x160]'])}

def evidence(io_dir,ge_dir,pending_dir):
    out=[]
    for addr,spec in EVIDENCE.items():
        root={'ge':ge_dir,'io':io_dir,'pending':pending_dir}[spec[0]]
        out.append(check_evidence(Path(root)/(addr+'.private.json'),addr,spec,GE_SHA if spec[0] in ('ge','pending') else IO_SHA))
    return out

def sdk_check():
    sdk=subprocess.check_output(['xcrun','--show-sdk-path'],text=True,timeout=30).strip()
    ver=subprocess.check_output(['xcrun','--show-sdk-version'],text=True,timeout=30).strip()
    if ver!='26.2':raise ValueError('Qualified SDK version differs')
    hdr=Path(sdk)/'System/Library/Frameworks/Kernel.framework/Headers'
    source=Path(__file__).with_name('video_shared_delete_layout.cpp')
    command=['xcrun','clang++','-arch','x86_64','-std=c++17','-fsyntax-only','-DKERNEL','-I',str(hdr),str(source)]
    result=subprocess.run(command,capture_output=True,text=True,timeout=60)
    if result.returncode:raise ValueError('Kernel SDK layout assertions failed: '+result.stderr[:1000])
    return {'SDK_version':ver,'source_SHA256':digest(source.read_bytes()),
            'header_SHA256':digest((hdr/'IOKit/IOUserClient.h').read_bytes()),'compile':'PASS',
            'scalarInput_offset':32,'scalarInputCount_offset':40,'compiled_only':True}

def user_release_check(cache_path,finalizer,out_parent):
    cache_path=cache_path.resolve()
    if file_sha(cache_path)!=CACHE_SHA:raise ValueError('Pinned user-mode cache differs')
    c=Cache(cache_path);img,starts=inspect(c,image_map(cache_path.with_name(cache_path.name+'.map'),IMAGE)[0]['start'],IMAGE)
    if img['UUID']!=UUID:raise ValueError('User-mode image UUID differs')
    meta=json.loads((finalizer/'metadata.json').read_text());r=meta['region'];b=(finalizer/'function-region.private.bin').read_bytes()
    start=0x7ff80f88f6a5;expected='17f9d42efe9b91891078eebb6dbe32fd90fd00fcf542079507ec5ba3d4cde3f7'
    if (meta['status']!='PASS' or meta['image']['UUID']!=UUID or not meta['region_captured_privately'] or
        r['start_VM']!=start or r['target_VM']!=start or r['end_VM']!=start+len(b) or r['boundary_source']!='LC_FUNCTION_STARTS' or
        r['SHA256']!=expected or digest(b)!=expected or start not in starts or digest(c.read(start,len(b)))!=expected):
        raise ValueError('Pinned resource finalizer differs')
    target=branch(b,start,0x7ff80f88f745,0xe8);binding=stub_symbol(c,img,target)
    if target!=0x7ff80f89475e or not binding or binding.get('static_symbol')!='_IOConnectCallMethod':
        raise ValueError('Resource release method binding differs')
    with tempfile.TemporaryDirectory(prefix='video-shared-delete-',dir=out_parent) as temp:
        obj=Path(temp)/'analysis.private.o'
        subprocess.run([sys.executable,str(Path(__file__).with_name('video_region_analysis_object.py')),'--metadata',str(finalizer/'metadata.json'),'--out',str(obj)],check=True,capture_output=True,timeout=30)
        text=subprocess.run(['xcrun','llvm-objdump','-d','--x86-asm-syntax=intel',str(obj)],check=True,capture_output=True,text=True,timeout=30).stdout
    anchors=[r'mov\s+rax, qword ptr \[rdi \+ 0x48\]',r'mov\s+eax, dword ptr \[rax \+ 0x100\]',
             r'mov\s+qword ptr \[rbp - 0x10\], rax',r'lea\s+rdx, \[rbp - 0x10\]',
             r'mov\s+esi, 0x1',r'mov\s+ecx, 0x1']
    if not all(re.search(x,text) for x in anchors):raise ValueError('Native release arguments differ')
    return {'cache_SHA256':CACHE_SHA,'image_UUID':UUID,'finalizer_SHA256':expected,
            'selector':1,'scalar_input_count':1,'value_source':'32-bit field at offset 0x100 in resource-associated client data',
            'runtime_binding_observed':False,'selector_invoked':False}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('ioaccel','geforce','io-rea','ge-rea','pending-rea','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--sdk-check',action='store_true')
    p.add_argument('--cache',type=Path)
    p.add_argument('--finalizer',type=Path)
    a=p.parse_args()
    if a.out.exists() or not a.out.parent.is_dir():raise ValueError('Fresh output file required')
    if bool(a.cache)!=bool(a.finalizer):raise ValueError('cache and finalizer must be provided together')
    r=static_tables(a.ioaccel,a.geforce);r['REA_evidence']=evidence(a.io_rea,a.ge_rea,a.pending_rea);r['SDK_layout']=sdk_check() if a.sdk_check else None
    r['native_resource_release']=user_release_check(a.cache,a.finalizer,a.out.parent) if a.cache else None;r['status']='PASS'
    with a.out.open('x') as f:json.dump(r,f,indent=2);f.write('\n')
    print(json.dumps({'status':'PASS','selector':1,'runtime_dispatch_observed':False,'native_calls':0}))

if __name__=='__main__':main()
